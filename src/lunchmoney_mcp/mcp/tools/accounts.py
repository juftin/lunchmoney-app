"""FastMCP tools for manual and Plaid account operations."""

from typing import TYPE_CHECKING

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import AccountInfo, AccountsSummary
from lunchmoney_mcp.services import (
    fetch_accounts,
    fetch_manual_account_by_id,
    fetch_plaid_account_by_id,
)

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyDatabase


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
async def get_manual_account(account_id: int) -> AccountInfo | None:
    """Fetch one synchronized manual account.

    Parameters
    ----------
    account_id : int
        Identifier of the manual account to retrieve.

    Returns
    -------
    AccountInfo | None
        Matching account, or ``None`` when it has not been synchronized.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_manual_account_by_id(db=db, account_id=account_id)


@mcp.tool()
async def get_plaid_account(account_id: int) -> AccountInfo | None:
    """Fetch one synchronized Plaid account.

    Parameters
    ----------
    account_id : int
        Identifier of the Plaid account to retrieve.

    Returns
    -------
    AccountInfo | None
        Matching account, or ``None`` when it has not been synchronized.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_plaid_account_by_id(db=db, account_id=account_id)


__all__ = ["get_manual_account", "get_plaid_account", "list_accounts"]
