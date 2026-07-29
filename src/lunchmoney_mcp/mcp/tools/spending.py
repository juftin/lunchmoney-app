"""FastMCP tools for grouped spending analysis operations."""

import datetime
from typing import TYPE_CHECKING

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import GroupedSpendingResponse
from lunchmoney_mcp.services import fetch_category_spending

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyDatabase


@mcp.tool()
async def get_category_spending(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    days: int | None = 30,
) -> GroupedSpendingResponse:
    """Fetch grouped spending analysis by category over specified date range.

    Parameters
    ----------
    start_date : datetime.date | None
        Optional start date for transaction filtering.
    end_date : datetime.date | None
        Optional end date for transaction filtering.
    days : int | None
        Number of past days to query if start_date is omitted. Default is 30.

    Returns
    -------
    GroupedSpendingResponse
        Grouped spending report with parent/child category rollups and totals.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_category_spending(
        db=db, start_date=start_date, end_date=end_date, days=days
    )


__all__ = ["get_category_spending"]
