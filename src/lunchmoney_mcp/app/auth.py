"""API-key protection for the REST application."""

import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from lunchmoney_mcp.config import get_settings


async def verify_api_key(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Require the configured API key for REST requests when one is configured.

    Parameters
    ----------
    request : Request
        Incoming REST request whose ``X-API-Key`` header is checked.
    call_next : Callable[[Request], Awaitable[Response]]
        ASGI continuation used for authorized requests.

    Returns
    -------
    Response
        The downstream response, or a 401 response for missing or invalid keys.
    """
    if request.url.path.startswith("/mcp"):
        return await call_next(request)

    expected_key = get_settings().lunchmoney_mcp_api_key
    provided_key = request.headers.get("X-API-Key")
    if expected_key is not None and not secrets.compare_digest(
        provided_key or "", expected_key
    ):
        return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
    return await call_next(request)


__all__ = ["verify_api_key"]
