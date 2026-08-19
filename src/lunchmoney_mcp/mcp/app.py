"""Central FastMCP application instance definition for Lunch Money operations."""

from collections.abc import AsyncIterator

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.app.auth import get_mcp_oauth_provider
from lunchmoney_mcp.config import get_runtime_mode, get_settings
from lunchmoney_mcp.mcp.operations import DataOperationMiddleware


@lifespan
async def mcp_lifespan(_: FastMCP[None]) -> AsyncIterator[dict[str, object]]:
    """Own ephemeral storage only while the standalone MCP runtime is active."""
    if get_runtime_mode() != "mcp" or get_settings().ephemeral:
        yield {}
        return

    database = get_database()
    await database.create_tables()
    try:
        yield {}
    finally:
        await database.dispose()
        get_database.cache_clear()  # type: ignore[attr-defined]


mcp: FastMCP[None] = FastMCP(
    "Lunch Money MCP",
    auth=get_mcp_oauth_provider(),
    lifespan=mcp_lifespan,
)
"""Application-wide FastMCP server instance."""

mcp.add_middleware(DataOperationMiddleware())
