"""Tests for HTTP network-hardening middleware."""

import asyncio

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from lunchmoney_app.app.security import (
    RequestBodyLimitMiddleware,
    apply_security_middleware,
)
from lunchmoney_app.config import RuntimeSettings


def build_test_app(settings: RuntimeSettings) -> FastAPI:
    """Create a small HTTP app protected by the supplied network policy."""
    app = FastAPI()

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        """Return a fixed successful response for middleware tests."""
        return {"status": "ok"}

    @app.post("/echo")
    async def echo(body: bytes) -> dict[str, int]:
        """Force FastAPI to read a request body for streaming-limit coverage."""
        return {"length": len(body)}

    @app.get("/slow")
    async def slow() -> dict[str, str]:
        """Delay long enough for the configured timeout policy to intervene."""
        await asyncio.sleep(0.02)
        return {"status": "late"}

    apply_security_middleware(app=app, settings=settings)
    return app


def test_network_policy_rejects_unknown_hosts() -> None:
    """Require a configured Host header before serving a request."""
    app = build_test_app(RuntimeSettings(allowed_hosts="api.example.com"))

    with TestClient(app, base_url="http://api.example.com") as client:
        assert client.get("/ok").status_code == 200
    with TestClient(app, base_url="http://untrusted.example.com") as client:
        assert client.get("/ok").status_code == 400


def test_network_policy_rejects_oversized_bodies() -> None:
    """Reject a payload from its declared Content-Length before application parsing."""
    app = build_test_app(
        RuntimeSettings(allowed_hosts="localhost", max_request_body_bytes=4)
    )

    with TestClient(app, base_url="http://localhost") as client:
        response = client.post("/echo", content=b"12345")

    assert response.status_code == 413
    assert response.json() == {
        "detail": "Request body exceeds the configured size limit"
    }


@pytest.mark.asyncio
async def test_stream_limit_does_not_start_a_second_response() -> None:
    """Do not emit a replacement response after downstream headers were sent."""
    sent: list[dict[str, object]] = []

    async def downstream(scope: object, receive: object, send: object) -> None:
        """Start a response before consuming the oversized request body."""
        del scope
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await receive()

    async def receive() -> dict[str, object]:
        """Return one streamed chunk exceeding the configured limit."""
        return {"type": "http.request", "body": b"12345", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        """Capture downstream ASGI messages."""
        sent.append(message)

    middleware = RequestBodyLimitMiddleware(downstream, max_body_bytes=4)
    await middleware({"type": "http", "headers": []}, receive, send)

    assert [message["type"] for message in sent] == ["http.response.start"]


def test_network_policy_times_out_slow_requests() -> None:
    """End requests that exceed their explicitly configured execution budget."""
    app = build_test_app(
        RuntimeSettings(allowed_hosts="localhost", request_timeout_seconds=0.001)
    )

    with TestClient(app, base_url="http://localhost") as client:
        response = client.get("/slow")

    assert response.status_code == 504
    assert response.json() == {"detail": "Request exceeded the configured timeout"}


def test_network_policy_rate_limits_each_client() -> None:
    """Reject requests beyond the fixed-window per-client allowance."""
    app = build_test_app(
        RuntimeSettings(
            allowed_hosts="localhost",
            rate_limit_requests=1,
            rate_limit_window_seconds=60,
        )
    )

    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/ok").status_code == 200
        response = client.get("/ok")

    assert response.status_code == 429
    assert response.json() == {"detail": "Rate limit exceeded"}
