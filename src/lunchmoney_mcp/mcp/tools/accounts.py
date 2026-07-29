"""FastMCP tools for manual and Plaid account operations."""

import datetime
from typing import TYPE_CHECKING

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import (
    AccountInfo,
    AccountsSummary,
    ManualAccountCreateRequest,
    ManualAccountUpdateRequest,
)
from lunchmoney_mcp.services import (
    create_manual_account as create_manual_account_service,
    delete_manual_account as delete_manual_account_service,
    fetch_accounts,
    fetch_manual_account_by_id,
    fetch_plaid_account_by_id,
    trigger_plaid_fetch as trigger_plaid_fetch_service,
    update_manual_account as update_manual_account_service,
)

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyDatabase, LunchMoneyApp


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


@mcp.tool()
async def create_manual_account(
    request: ManualAccountCreateRequest,
) -> AccountInfo:
    """Create a manual account and cache Lunch Money's canonical response."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await create_manual_account_service(client=client, db=db, request=request)


@mcp.tool()
async def update_manual_account(
    account_id: int,
    request: ManualAccountUpdateRequest,
) -> AccountInfo:
    """Update a manual account and cache Lunch Money's canonical response."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await update_manual_account_service(
        client=client,
        db=db,
        account_id=account_id,
        request=request,
    )


@mcp.tool()
async def delete_manual_account(
    account_id: int,
    delete_items: bool | None = None,
    delete_balance_history: bool | None = None,
) -> None:
    """Delete a manual account upstream and remove its cached row."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    await delete_manual_account_service(
        client=client,
        db=db,
        account_id=account_id,
        delete_items=delete_items,
        delete_balance_history=delete_balance_history,
    )


@mcp.tool()
async def trigger_plaid_fetch(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    account_id: int | None = None,
) -> None:
    """Trigger a Lunch Money transaction fetch for eligible Plaid accounts."""
    client: LunchMoneyApp = get_lunchmoney_app()
    await trigger_plaid_fetch_service(
        client=client,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
    )


__all__ = [
    "create_manual_account",
    "delete_manual_account",
    "get_manual_account",
    "get_plaid_account",
    "list_accounts",
    "trigger_plaid_fetch",
    "update_manual_account",
]
