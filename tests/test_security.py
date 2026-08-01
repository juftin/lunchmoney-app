"""Tests for HTTP network-hardening middleware."""

import asyncio

from fastapi import FastAPI
from starlette.testclient import TestClient

from lunchmoney_mcp.app.security import apply_security_middleware
from lunchmoney_mcp.config import RuntimeSettings


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
