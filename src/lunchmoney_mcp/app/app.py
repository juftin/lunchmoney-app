"""
FastAPI application for Lunch Money MCP.
"""

import logging
from typing import Annotated, Any

from fastapi import Depends, FastAPI
from fastmcp import FastMCP
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.utilities.lifespan import combine_lifespans

from lunchmoney_mcp.client import LunchMoneyApp, SyncSummary
from lunchmoney_mcp.database import LunchMoneyDatabase, run_migrations
from lunchmoney_mcp.app.dependencies import (
    get_database,
    get_db_session,
    get_lunchmoney_app,
)
from lunchmoney_mcp.app.lifespan import lifespan
from lunchmoney_mcp.app.sync import sync_database

import sys

logger = logging.getLogger(__name__)


def _resolve_sync_database() -> Any:
    """Resolve sync_database function, respecting monkeypatches on lunchmoney_mcp.app."""
    app_module = sys.modules.get("lunchmoney_mcp.app")
    if app_module is not None and hasattr(app_module, "sync_database"):
        return getattr(app_module, "sync_database")
    return sync_database


fastapi_app = FastAPI(
    title="Lunch Money MCP",
    description="Lunch Money Model Context Protocol Server & API",
    lifespan=lifespan,
)


@fastapi_app.get(path="/")
async def root() -> dict[str, object]:
    """Root endpoint returning Hello World."""
    return {
        "message": "Hello World",
    }


@fastapi_app.post(path="/sync")
async def sync(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    app: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    days: int = 30,
) -> dict[str, object]:
    """Run database migrations and synchronize Lunch Money data for specified date window."""
    logger.info("Triggering database migrations and %s-day sync...", days)
    await run_migrations()
    fn = _resolve_sync_database()
    summary: SyncSummary = await fn(db=db, client=app, days=days)
    return {
        "message": "Synchronization complete",
        "synced": summary,
    }


mcp: FastMCP[Any] = FastMCP.from_fastapi(app=fastapi_app)
mcp_app: StarletteWithLifespan = mcp.http_app(path="/mcp")
app = FastAPI(
    routes=[
        *mcp_app.routes,
        *fastapi_app.routes,
    ],
    lifespan=combine_lifespans(mcp_app.lifespan, lifespan),
)

__all__: list[str] = [
    "app",
    "fastapi_app",
    "get_database",
    "get_db_session",
    "get_lunchmoney_app",
    "lifespan",
    "mcp",
    "mcp_app",
    "run_migrations",
    "sync_database",
]

if __name__ == "__main__":
    mcp.run()
