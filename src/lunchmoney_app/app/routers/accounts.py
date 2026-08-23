"""Account endpoints."""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import ManualAccountObject, PlaidAccountObject

from lunchmoney_app.app.dependencies import OperationContext, get_operation_context
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

router = APIRouter(tags=["Accounts"])


@router.get(
    path="/accounts", response_model=AccountsSummary, operation_id="list_accounts"
)
async def list_accounts(
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> AccountsSummary:
    """List complete manual and Plaid account collections."""
    return await fetch_accounts(context)


@router.get(
    path="/manual_accounts",
    response_model=list[ManualAccountObject],
    operation_id="list_manual_accounts",
)
async def list_manual_accounts(
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> list[ManualAccountObject]:
    """List all manual accounts."""
    return await fetch_manual_accounts(context)


@router.get(
    path="/plaid_accounts",
    response_model=list[PlaidAccountObject],
    operation_id="list_plaid_accounts",
)
async def list_plaid_accounts(
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> list[PlaidAccountObject]:
    """List all Plaid accounts."""
    return await fetch_plaid_accounts(context)


@router.get(
    path="/manual_accounts/{id}",
    response_model=ManualAccountObject | None,
    operation_id="get_manual_account",
)
async def get_manual_account(
    id: int,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> ManualAccountObject | None:
    """Return one manual account when available."""
    return await fetch_manual_account_by_id(context, id)


@router.get(
    path="/plaid_accounts/{id}",
    response_model=PlaidAccountObject | None,
    operation_id="get_plaid_account",
)
async def get_plaid_account(
    id: int,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> PlaidAccountObject | None:
    """Return one Plaid account when available."""
    return await fetch_plaid_account_by_id(context, id)


@router.post(
    path="/manual_accounts",
    response_model=ManualAccountObject,
    operation_id="create_manual_account",
)
async def create_manual_account(
    request: ManualAccountCreateRequest,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> ManualAccountObject:
    """Create a manual account."""
    return await create_manual_account_service(context, request)


@router.put(
    path="/manual_accounts/{id}",
    response_model=ManualAccountObject,
    operation_id="update_manual_account",
)
async def update_manual_account(
    id: int,
    request: ManualAccountUpdateRequest,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> ManualAccountObject:
    """Update a manual account."""
    return await update_manual_account_service(context, id, request)


@router.delete(
    path="/manual_accounts/{id}", status_code=204, operation_id="delete_manual_account"
)
async def delete_manual_account(
    id: int,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
    delete_items: bool | None = None,
    delete_balance_history: bool | None = None,
) -> None:
    """Delete a manual account."""
    await delete_manual_account_service(
        context, id, delete_items, delete_balance_history
    )


@router.post(
    path="/plaid_accounts/fetch", status_code=204, operation_id="trigger_plaid_fetch"
)
async def trigger_plaid_fetch(
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    id: int | None = None,
) -> None:
    """Trigger a Lunch Money transaction fetch for eligible Plaid accounts."""
    await trigger_plaid_fetch_service(context, start_date, end_date, id)
