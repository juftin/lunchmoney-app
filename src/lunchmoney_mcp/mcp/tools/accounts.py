"""FastMCP tools for manual and Plaid account operations."""

from typing import TYPE_CHECKING

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import AccountsSummary
from lunchmoney_mcp.services import fetch_accounts

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


__all__ = ["list_accounts"]
