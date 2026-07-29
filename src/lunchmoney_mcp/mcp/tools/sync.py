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
async def sync_data(days: int = 30) -> SyncResult:
    """Synchronize transactions, accounts, categories, and tags from Lunch Money API.

    Parameters
    ----------
    days : int
        Number of days back from today to synchronize. Default is 30.

    Returns
    -------
    SyncResult
        Summary of synchronized records.
    """
    db: LunchMoneyDatabase = get_database()
    client: LunchMoneyApp = get_lunchmoney_app()
    return await execute_mcp_sync(db=db, client=client, days=days)


__all__ = ["sync_data"]
