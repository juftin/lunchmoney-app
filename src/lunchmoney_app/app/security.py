"""ASGI middleware enforcing bounded, secure HTTP runtime policies."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from lunchmoney_app.config import RuntimeSettings

ASGIApp = Callable[
    [
        dict[str, Any],
        Callable[[], Awaitable[dict[str, Any]]],
        Callable[[dict[str, Any]], Awaitable[None]],
    ],
    Awaitable[None],
]
"""Callable protocol shape accepted by the small ASGI middleware classes."""


async def _send_json_error(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    status_code: int,
    detail: str,
) -> None:
    """Send a minimal safe JSON error response without request-derived content."""
    body = f'{{"detail":"{detail}"}}'.encode()
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class RequestBodyTooLargeError(Exception):
    """Signal that streamed request data exceeded the configured body limit."""


class RequestBodyLimitMiddleware:
    """Reject both declared and streamed request bodies larger than the limit."""

    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        """Create a body-size guard for one ASGI application.

        Parameters
        ----------
        app : ASGIApp
            Wrapped application.
        max_body_bytes : int
            Largest accepted request payload in bytes.
        """
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Apply the body-size limit to HTTP requests while preserving other scopes."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = next(
            (
                value
                for name, value in scope["headers"]
                if name.lower() == b"content-length"
            ),
            None,
        )
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = 0
            if declared_length > self.max_body_bytes:
                await _send_json_error(
                    send,
                    status_code=413,
                    detail="Request body exceeds the configured size limit",
                )
                return

        received_bytes = 0

        async def limited_receive() -> dict[str, Any]:
            """Count streamed body chunks before the downstream application reads them."""
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_bytes:
                    raise RequestBodyTooLargeError
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLargeError:
            await _send_json_error(
                send,
                status_code=413,
                detail="Request body exceeds the configured size limit",
            )


class RequestTimeoutMiddleware:
    """Bound request execution time and return a safe timeout response."""

    def __init__(self, app: ASGIApp, timeout_seconds: float) -> None:
        """Create a timeout guard for one ASGI application."""
        self.app = app
        self.timeout_seconds = timeout_seconds

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Cancel an overlong HTTP request before it can exhaust a worker."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response_started = False

        async def tracked_send(message: dict[str, Any]) -> None:
            """Track whether an application response can still be safely replaced."""
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await asyncio.wait_for(
                self.app(scope, receive, tracked_send), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            if not response_started:
                await _send_json_error(
                    send,
                    status_code=504,
                    detail="Request exceeded the configured timeout",
                )


class ConcurrencyLimitMiddleware:
    """Reject excess in-flight HTTP requests instead of queuing unbounded work."""

    def __init__(self, app: ASGIApp, max_concurrent_requests: int) -> None:
        """Create a per-process concurrent-request guard."""
        self.app = app
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Serve only requests that fit in the configured concurrency budget."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self.semaphore.locked():
            await _send_json_error(
                send,
                status_code=503,
                detail="Server is at its configured concurrency limit",
            )
            return
        await self.semaphore.acquire()
        try:
            await self.app(scope, receive, send)
        finally:
            self.semaphore.release()


class RateLimitMiddleware:
    """Apply an in-memory fixed-window request limit per resolved client IP."""

    _MAX_TRACKED_CLIENTS: int = 10_000
    """Maximum client buckets retained by one worker to bound limiter memory use."""

    def __init__(self, app: ASGIApp, requests: int, window_seconds: int) -> None:
        """Create a bounded fixed-window rate limiter for one process."""
        self.app = app
        self.requests = requests
        self.window_seconds = window_seconds
        self.requests_by_client: dict[str, deque[float]] = {}

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Reject a client once it has consumed its current request budget."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        now = time.monotonic()
        client = scope.get("client")
        client_ip = client[0] if client is not None else "unknown"
        timestamps = self.requests_by_client.get(client_ip)
        if timestamps is None:
            if len(self.requests_by_client) >= self._MAX_TRACKED_CLIENTS:
                self.requests_by_client.pop(next(iter(self.requests_by_client)))
            timestamps = deque()
            self.requests_by_client[client_ip] = timestamps
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()
        if len(timestamps) >= self.requests:
            await _send_json_error(
                send,
                status_code=429,
                detail="Rate limit exceeded",
            )
            return
        timestamps.append(now)
        await self.app(scope, receive, send)


def apply_security_middleware(app: FastAPI, settings: RuntimeSettings) -> None:
    """Install secure HTTP policies on the combined REST and MCP application.

    Parameters
    ----------
    app : FastAPI
        Top-level application receiving REST and MCP traffic.
    settings : RuntimeSettings
        Validated deployment policy configuration.
    """
    if settings.cors_allowed_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allowed_origin_list),
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_bytes=settings.max_request_body_bytes,
    )
    app.add_middleware(
        RequestTimeoutMiddleware,
        timeout_seconds=settings.request_timeout_seconds,
    )
    app.add_middleware(
        ConcurrencyLimitMiddleware,
        max_concurrent_requests=settings.max_concurrent_requests,
    )
    app.add_middleware(
        RateLimitMiddleware,
        requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(settings.allowed_host_list)
    )
    if settings.trusted_proxy_ip_list:
        app.add_middleware(
            ProxyHeadersMiddleware,
            trusted_hosts=list(settings.trusted_proxy_ip_list),
        )


__all__ = [
    "ConcurrencyLimitMiddleware",
    "RateLimitMiddleware",
    "RequestBodyLimitMiddleware",
    "RequestTimeoutMiddleware",
    "apply_security_middleware",
]
