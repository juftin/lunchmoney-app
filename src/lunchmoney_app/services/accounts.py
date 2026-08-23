"""Service logic for account operations."""

import datetime

from lunchmoney.models import ManualAccountObject, PlaidAccountObject

from lunchmoney_app.schemas import (
    AccountsSummary,
    ManualAccountCreateRequest,
    ManualAccountUpdateRequest,
)
from lunchmoney_app.services.operations import OperationContext


async def fetch_accounts(context: OperationContext) -> AccountsSummary:
    """Return complete manual and Plaid account collections."""
    return await context.accounts.list()


async def fetch_manual_accounts(context: OperationContext) -> list[ManualAccountObject]:
    """Return all manual accounts from the selected reader."""
    return await context.accounts.list_manual()


async def fetch_plaid_accounts(context: OperationContext) -> list[PlaidAccountObject]:
    """Return all Plaid accounts from the selected reader."""
    return await context.accounts.list_plaid()


async def fetch_manual_account_by_id(
    context: OperationContext, account_id: int
) -> ManualAccountObject | None:
    """Return one manual account when available."""
    return await context.accounts.get_manual(account_id)


async def fetch_plaid_account_by_id(
    context: OperationContext, account_id: int
) -> PlaidAccountObject | None:
    """Return one Plaid account when available."""
    return await context.accounts.get_plaid(account_id)


async def create_manual_account(
    context: OperationContext,
    request: ManualAccountCreateRequest,
) -> ManualAccountObject:
    """Create a manual account upstream, then apply mode-specific projection."""
    account = await context.client.client.manual_accounts.create_manual_account(
        create_manual_account_request_object=request.to_api()
    )
    await context.project("accounts", context.accounts.store_manual(account))
    return account


async def update_manual_account(
    context: OperationContext,
    account_id: int,
    request: ManualAccountUpdateRequest,
) -> ManualAccountObject:
    """Update a manual account upstream, then apply mode-specific projection."""
    account = await context.client.client.manual_accounts.update_manual_account(
        id=account_id,
        update_manual_account_request_object=request.to_api(),
    )
    await context.project("accounts", context.accounts.store_manual(account))
    return account


async def delete_manual_account(
    context: OperationContext,
    account_id: int,
    delete_items: bool | None = None,
    delete_balance_history: bool | None = None,
) -> None:
    """Delete a manual account upstream, then reconcile selected state."""
    await context.client.client.manual_accounts.delete_manual_account(
        id=account_id,
        delete_items=delete_items,
        delete_balance_history=delete_balance_history,
    )
    await context.project(
        "accounts",
        context.accounts.delete_manual(account_id, delete_items is True),
    )


async def trigger_plaid_fetch(
    context: OperationContext,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    account_id: int | None = None,
) -> None:
    """Ask Lunch Money to fetch recent Plaid transactions."""
    await context.client.client.plaid.trigger_plaid_account_fetch(
        start_date=start_date,
        end_date=end_date,
        id=account_id,
    )
    await context.project(
        "accounts",
        context.accounts.invalidate_after_plaid_fetch(),
    )
