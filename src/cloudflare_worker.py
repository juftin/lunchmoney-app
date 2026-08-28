"""Cloudflare Worker entrypoint for the Lunch Money MCP ASGI application."""

from os import environ
from typing import Any

from workers import WorkerEntrypoint, asgi, env

for name in (
    "LUNCHMONEY_ACCESS_TOKEN",
    "LUNCHMONEY_ENVIRONMENT",
    "LUNCHMONEY_PERSISTENCE_MODE",
):
    if value := getattr(env, name, None):
        environ[name] = str(value)

_app: Any | None = None


def get_app() -> Any:
    """Create the MCP ASGI application once, inside a request context."""
    global _app
    if _app is None:
        from lunchmoney_app.mcp import mcp

        _app = mcp.http_app(path="/mcp")
    return _app


class Default(WorkerEntrypoint):
    """Serve the Streamable HTTP MCP application at ``/mcp`` only."""

    async def fetch(self, request: Any) -> Any:
        """Adapt an incoming Cloudflare request to the MCP ASGI application."""
        return await asgi.fetch(get_app(), request, self.env, self.ctx)
