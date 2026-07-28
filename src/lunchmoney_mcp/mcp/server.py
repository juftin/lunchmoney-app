"""FastMCP server instance and parallel tool definitions for Lunch Money operations."""

from fastmcp import FastMCP

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.schemas import (
    AccountsSummary,
    CategoryInfo,
    SyncResult,
    TransactionInfo,
    UserInfo,
)
from lunchmoney_mcp.services import (
    execute_mcp_sync,
    fetch_accounts,
    fetch_categories,
    fetch_recent_transactions,
    fetch_user_info,
)

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
    db = get_database()
    client = get_lunchmoney_app()
    return await execute_mcp_sync(db=db, client=client, days=days)


@mcp.tool()
async def get_user_info() -> UserInfo | None:
    """Fetch the authenticated user profile and budget details.

    Returns
    -------
    UserInfo | None
        User profile details or None if no user profile exists in database.
    """
    db = get_database()
    return await fetch_user_info(db=db)


@mcp.tool()
async def list_categories() -> list[CategoryInfo]:
    """List all budget categories and subcategories.

    Returns
    -------
    list[CategoryInfo]
        List of all budget category objects in database.
    """
    db = get_database()
    return await fetch_categories(db=db)


@mcp.tool()
async def list_accounts() -> AccountsSummary:
    """List all connected Plaid and manual accounts with current balances.

    Returns
    -------
    AccountsSummary
        Summary of connected Plaid and manual accounts.
    """
    db = get_database()
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
    db = get_database()
    return await fetch_recent_transactions(db=db, days=days, limit=limit)


__all__ = [
    "get_recent_transactions",
    "get_user_info",
    "list_accounts",
    "list_categories",
    "mcp",
    "sync_data",
]
