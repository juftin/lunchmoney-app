"""FastMCP server instance and parallel tool definitions for Lunch Money operations."""

import datetime
from typing import TYPE_CHECKING

from fastmcp import FastMCP

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.schemas import (
    AccountsSummary,
    CategoryInfo,
    GroupedSpendingResponse,
    SyncResult,
    TransactionInfo,
    UserInfo,
)
from lunchmoney_mcp.services import (
    execute_mcp_sync,
    fetch_accounts,
    fetch_categories,
    fetch_category_spending,
    fetch_recent_transactions,
    fetch_user_info,
)

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyDatabase
    from lunchmoney_mcp.client import LunchMoneyApp

mcp: FastMCP[None] = FastMCP("Lunch Money MCP")


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


@mcp.tool()
async def get_user_info() -> UserInfo | None:
    """Fetch the authenticated user profile and budget details.

    Returns
    -------
    UserInfo | None
        User profile details or None if no user profile exists in database.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_user_info(db=db)


@mcp.tool()
async def list_categories() -> list[CategoryInfo]:
    """List all budget categories and subcategories.

    Returns
    -------
    list[CategoryInfo]
        List of all budget category objects in database.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_categories(db=db)


@mcp.tool()
async def list_accounts() -> AccountsSummary:
    """List all connected Plaid and manual accounts with current balances.

    Returns
    -------
    AccountsSummary
        Summary of connected Plaid and manual accounts.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_accounts(db=db)


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


__all__ = [
    "get_category_spending",
    "get_recent_transactions",
    "get_user_info",
    "list_accounts",
    "list_categories",
    "mcp",
    "sync_data",
]
