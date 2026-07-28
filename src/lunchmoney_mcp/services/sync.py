"""Service logic for Lunch Money database synchronization."""

import logging

from lunchmoney_mcp.app.sync import sync_database
from lunchmoney_mcp.client import LunchMoneyApp, SyncSummary
from lunchmoney_mcp.database import LunchMoneyDatabase, run_migrations
from lunchmoney_mcp.schemas import SyncDetails, SyncResponse, SyncResult

logger = logging.getLogger(__name__)


async def execute_sync(
    db: LunchMoneyDatabase, client: LunchMoneyApp, days: int = 30
) -> SyncResponse:
    """Run database migrations and synchronize Lunch Money data.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    client : LunchMoneyApp
        Lunch Money API client wrapper.
    days : int
        Number of past calendar days to pull transactions for. Default is 30.

    Returns
    -------
    SyncResponse
        Status summary and record counts of synchronized objects.
    """
    logger.info("Triggering database migrations and %s-day sync...", days)
    await run_migrations()
    summary: SyncSummary = await sync_database(db=db, client=client, days=days)
    details = SyncDetails(
        user=summary.user,
        plaid_accounts=summary.plaid_accounts,
        manual_accounts=summary.manual_accounts,
        categories=summary.categories,
        tags=summary.tags,
        transactions=summary.transactions,
        total=summary.total,
    )
    return SyncResponse(message="Synchronization complete", synced=details)


async def execute_mcp_sync(
    db: LunchMoneyDatabase, client: LunchMoneyApp, days: int = 30
) -> SyncResult:
    """Execute sync for MCP tool returning SyncResult schema.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    client : LunchMoneyApp
        Lunch Money API client wrapper.
    days : int
        Number of past calendar days to pull transactions for. Default is 30.

    Returns
    -------
    SyncResult
        MCP tool result format.
    """
    response = await execute_sync(db=db, client=client, days=days)
    return SyncResult(status="success", synced_records=response.synced)
