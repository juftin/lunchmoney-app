"""Synchronization API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.app.sync import sync_database
from lunchmoney_mcp.client import LunchMoneyApp, SyncSummary
from lunchmoney_mcp.database import LunchMoneyDatabase, run_migrations
from lunchmoney_mcp.schemas import SyncDetails, SyncResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sync"])


@router.post(
    path="/sync",
    response_model=SyncResponse,
    operation_id="sync_database",
)
async def sync(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    days: int = 30,
) -> SyncResponse:
    """Run database migrations and synchronize Lunch Money data for specified date window."""
    logger.info("Triggering database migrations and %s-day sync...", days)
    await run_migrations()
    summary: SyncSummary = await sync_database(db=db, client=client, days=days)
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
