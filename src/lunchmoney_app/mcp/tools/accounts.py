"""FastMCP tools for manual and Plaid account operations."""

import datetime
from typing import TYPE_CHECKING

from lunchmoney.models import (
    ManualAccountObject,
    PlaidAccountObject,
)

from lunchmoney_app.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.schemas import (
    AccountsSummary,
    ManualAccountCreateRequest,
    ManualAccountUpdateRequest,
)
from lunchmoney_app.services import (
    create_manual_account as create_manual_account_service,
    delete_manual_account as delete_manual_account_service,
    fetch_accounts,
    fetch_manual_account_by_id,
    fetch_manual_accounts,
    fetch_plaid_account_by_id,
    fetch_plaid_accounts,
    trigger_plaid_fetch as trigger_plaid_fetch_service,
    update_manual_account as update_manual_account_service,
)

if TYPE_CHECKING:
    from lunchmoney_app import LunchMoneyDatabase, LunchMoneyApp


@mcp.tool()
async def list_accounts() -> AccountsSummary:
    """List complete synchronized manual and Plaid account collections.

    Returns
    -------
    AccountsSummary
        Full account objects separated into manual and Plaid collections.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_accounts(db=db)


@mcp.tool()
async def list_manual_accounts() -> list[ManualAccountObject]:
    """List synchronized manual accounts with every Lunch Money field.

    Returns
    -------
    list[ManualAccountObject]
        Complete synchronized manual-account objects.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_manual_accounts(db=db)


@mcp.tool()
async def list_plaid_accounts() -> list[PlaidAccountObject]:
    """List synchronized Plaid accounts with every Lunch Money field.

    Returns
    -------
    list[PlaidAccountObject]
        Complete synchronized Plaid-account objects.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_plaid_accounts(db=db)


@mcp.tool()
async def get_manual_account(account_id: int) -> ManualAccountObject | None:
    """Fetch one synchronized manual account.

    Parameters
    ----------
    account_id : int
        Identifier of the manual account to retrieve.

    Returns
    -------
    ManualAccountObject | None
        Matching account, or ``None`` when it has not been synchronized.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_manual_account_by_id(db=db, account_id=account_id)


@mcp.tool()
async def get_plaid_account(account_id: int) -> PlaidAccountObject | None:
    """Fetch one synchronized Plaid account.

    Parameters
    ----------
    account_id : int
        Identifier of the Plaid account to retrieve.

    Returns
    -------
    PlaidAccountObject | None
        Matching account, or ``None`` when it has not been synchronized.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_plaid_account_by_id(db=db, account_id=account_id)


@mcp.tool()
async def create_manual_account(
    request: ManualAccountCreateRequest,
) -> ManualAccountObject:
    """Create a manual account and cache Lunch Money's canonical response."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await create_manual_account_service(client=client, db=db, request=request)


@mcp.tool()
async def update_manual_account(
    account_id: int,
    request: ManualAccountUpdateRequest,
) -> ManualAccountObject:
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
    "list_manual_accounts",
    "list_plaid_accounts",
    "trigger_plaid_fetch",
    "update_manual_account",
]
