"""FastMCP tools for database synchronization operations."""

from typing import TYPE_CHECKING

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import SyncResult
from lunchmoney_mcp.services import execute_mcp_sync

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyDatabase
    from lunchmoney_mcp.client import LunchMoneyApp


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


__all__ = ["sync_data"]
