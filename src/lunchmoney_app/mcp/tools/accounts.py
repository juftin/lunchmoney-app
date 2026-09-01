"""FastMCP account tools."""

import datetime

from lunchmoney.models import ManualAccountObject, PlaidAccountObject

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
from lunchmoney_app.services.operations import get_operation_context


@mcp.tool()
async def list_accounts() -> AccountsSummary:
    """List complete manual and Plaid account collections."""
    return await fetch_accounts(get_operation_context())


@mcp.tool()
async def list_manual_accounts() -> list[ManualAccountObject]:
    """List all manual accounts."""
    return await fetch_manual_accounts(get_operation_context())


@mcp.tool()
async def list_plaid_accounts() -> list[PlaidAccountObject]:
    """List all Plaid accounts."""
    return await fetch_plaid_accounts(get_operation_context())


@mcp.tool()
async def get_manual_account(id: int) -> ManualAccountObject | None:
    """Return one manual account when available."""
    return await fetch_manual_account_by_id(get_operation_context(), id)


@mcp.tool()
async def get_plaid_account(id: int) -> PlaidAccountObject | None:
    """Return one Plaid account when available."""
    return await fetch_plaid_account_by_id(get_operation_context(), id)


@mcp.tool()
async def create_manual_account(
    request: ManualAccountCreateRequest,
) -> ManualAccountObject:
    """Create a manual account."""
    return await create_manual_account_service(get_operation_context(), request)


@mcp.tool()
async def update_manual_account(
    id: int, request: ManualAccountUpdateRequest
) -> ManualAccountObject:
    """Update a manual account."""
    return await update_manual_account_service(get_operation_context(), id, request)


@mcp.tool()
async def delete_manual_account(
    id: int,
    delete_items: bool | None = None,
    delete_balance_history: bool | None = None,
) -> None:
    """Delete a manual account."""
    await delete_manual_account_service(
        get_operation_context(), id, delete_items, delete_balance_history
    )


@mcp.tool()
async def trigger_plaid_fetch(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    id: int | None = None,
) -> None:
    """Trigger a Lunch Money Plaid transaction fetch."""
    await trigger_plaid_fetch_service(get_operation_context(), start_date, end_date, id)


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
