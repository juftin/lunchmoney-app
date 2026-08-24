"""Central FastMCP application instance definition for Lunch Money operations."""

from collections.abc import AsyncIterator

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from lunchmoney_app.app.dependencies import get_shared_database
from lunchmoney_app.app.auth import get_mcp_oauth_provider
from lunchmoney_app.config import (
    get_runtime_mode,
    get_secret_settings,
    get_settings,
    validate_persistence_configuration,
)
from lunchmoney_app.database import run_migrations
from lunchmoney_app.locks import LockTimeoutError, get_migration_lock
from lunchmoney_app.mcp.operations import DataOperationMiddleware


@lifespan
async def mcp_lifespan(_: FastMCP[None]) -> AsyncIterator[dict[str, object]]:
    """Initialize and dispose shared MCP storage for the selected mode."""
    validate_persistence_configuration(get_settings(), get_secret_settings())
    if get_runtime_mode() != "mcp" or get_settings().persistence_mode == "ephemeral":
        yield {}
        return

    database = get_shared_database()
    if database.database_url.startswith("sqlite") and (
        ":memory:" in database.database_url or "mode=memory" in database.database_url
    ):
        await database.create_tables()
    else:
        lock = get_migration_lock()
        try:
            with lock:
                await run_migrations(database_url=database.database_url)
        except LockTimeoutError:
            pass
    try:
        yield {}
    finally:
        await database.dispose()
        get_shared_database.cache_clear()


mcp: FastMCP[None] = FastMCP(
    "Lunch Money MCP",
    auth=get_mcp_oauth_provider(),
    lifespan=mcp_lifespan,
)
"""Application-wide FastMCP server instance."""

mcp.add_middleware(DataOperationMiddleware())
