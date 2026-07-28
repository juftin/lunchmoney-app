"""
FastAPI application for Lunch Money MCP.
"""

import logging
from typing import Annotated

from fastapi import Depends, FastAPI
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.utilities.lifespan import combine_lifespans

from lunchmoney_mcp.app.dependencies import (
    get_database,
    get_db_session,
    get_lunchmoney_app,
)
from lunchmoney_mcp.app.lifespan import lifespan
from lunchmoney_mcp.app.sync import sync_database
from lunchmoney_mcp.client import LunchMoneyApp, SyncSummary
from lunchmoney_mcp.database import LunchMoneyDatabase, run_migrations
from lunchmoney_mcp.mcp import mcp
from lunchmoney_mcp.schemas import RootResponse, SyncDetails, SyncResponse

logger = logging.getLogger(__name__)

fastapi_app = FastAPI(
    title="Lunch Money MCP",
    description="Lunch Money Model Context Protocol Server & API",
    lifespan=lifespan,
)


@fastapi_app.get(path="/", response_model=RootResponse)
async def root() -> RootResponse:
    """Root endpoint returning status message."""
    return RootResponse(message="Hello World")


@fastapi_app.post(path="/sync", response_model=SyncResponse)
async def sync(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    app: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    days: int = 30,
) -> SyncResponse:
    """Run database migrations and synchronize Lunch Money data for specified date window."""
    logger.info("Triggering database migrations and %s-day sync...", days)
    await run_migrations()
    summary: SyncSummary = await sync_database(db=db, client=app, days=days)
    return SyncResponse(
        message="Synchronization complete",
        synced=SyncDetails(
            user=summary.user,
            plaid_accounts=summary.plaid_accounts,
            manual_accounts=summary.manual_accounts,
            categories=summary.categories,
            tags=summary.tags,
            transactions=summary.transactions,
            total=summary.total,
        ),
    )


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
