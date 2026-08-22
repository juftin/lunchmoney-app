"""FastMCP tools for database synchronization operations."""

from typing import TYPE_CHECKING

from lunchmoney_app.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.schemas import ScheduledSyncStatus, SyncResult
from lunchmoney_app.services import execute_mcp_sync, get_scheduled_sync_status

if TYPE_CHECKING:
    from lunchmoney_app import LunchMoneyDatabase
    from lunchmoney_app.client import LunchMoneyApp


@mcp.tool()
async def sync_data(
    days: int = 30,
    incremental: bool = False,
    safety_margin_minutes: int | None = None,
) -> SyncResult:
    """Synchronize transactions, accounts, categories, and tags from Lunch Money API.

    Parameters
    ----------
    days : int
        Number of days back from today to synchronize. Default is 30.
    incremental : bool
        Whether to resume transaction sync from its successful watermark.
    safety_margin_minutes : int | None
        Optional overlap override for an incremental transaction sync.

    Returns
    -------
    SyncResult
        Summary of synchronized records.
    """
    db: LunchMoneyDatabase = get_database()
    client: LunchMoneyApp = get_lunchmoney_app()
    return await execute_mcp_sync(
        db=db,
        client=client,
        days=days,
        incremental=incremental,
        safety_margin_minutes=safety_margin_minutes,
    )


@mcp.tool()
async def get_sync_status() -> ScheduledSyncStatus | None:
    """Return the result of the latest attempted scheduled synchronization."""
    db: LunchMoneyDatabase = get_database()
    return await get_scheduled_sync_status(db=db)


__all__ = ["get_sync_status", "sync_data"]
