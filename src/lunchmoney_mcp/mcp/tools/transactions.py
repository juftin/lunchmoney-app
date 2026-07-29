"""FastMCP tools for transaction query and management operations."""

from typing import TYPE_CHECKING

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import TransactionInfo
from lunchmoney_mcp.services import fetch_recent_transactions

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyDatabase


@mcp.tool()
async def get_recent_transactions(
    days: int = 30, limit: int = 50
) -> list[TransactionInfo]:
    """Fetch recent transactions from local database within specified date window.

    Parameters
    ----------
    days : int
        Number of days back from today to include. Default is 30.
    limit : int
        Maximum number of transactions to return. Default is 50.

    Returns
    -------
    list[TransactionInfo]
        Filtered list of matching transaction objects ordered by date descending.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_recent_transactions(db=db, days=days, limit=limit)


__all__ = ["get_recent_transactions"]
