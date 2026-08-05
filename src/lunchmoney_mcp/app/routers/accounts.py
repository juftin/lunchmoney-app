"""Accounts data endpoints."""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import (
    ManualAccountObject,
    PlaidAccountObject,
)

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import (
    AccountsSummary,
    ManualAccountCreateRequest,
    ManualAccountUpdateRequest,
)
from lunchmoney_mcp.services import (
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
"""FastAPI APIRouter for financial accounts endpoints."""


@router.get(
    path="/accounts",
    response_model=AccountsSummary,
    operation_id="list_accounts",
)
async def list_accounts(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> AccountsSummary:
    """List complete synchronized manual and Plaid account collections.

    **Parameters:**

    - **db**: Database manager instance.

    **Returns:** Full account objects separated into manual and Plaid collections.
    """
    return await fetch_accounts(db=db)


@router.get(
    path="/manual_accounts",
    response_model=list[ManualAccountObject],
    operation_id="list_manual_accounts",
)
async def list_manual_accounts(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> list[ManualAccountObject]:
    """List synchronized manual accounts with every Lunch Money field.

    **Parameters:**

    - **db**: Database manager instance.

    **Returns:** Complete synchronized manual-account objects.
    """
    return await fetch_manual_accounts(db=db)


@router.get(
    path="/plaid_accounts",
    response_model=list[PlaidAccountObject],
    operation_id="list_plaid_accounts",
)
async def list_plaid_accounts(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> list[PlaidAccountObject]:
    """List synchronized Plaid accounts with every Lunch Money field.

    **Parameters:**

    - **db**: Database manager instance.

    **Returns:** Complete synchronized Plaid-account objects.
    """
    return await fetch_plaid_accounts(db=db)


@router.get(
    path="/manual_accounts/{id}",
    response_model=ManualAccountObject | None,
    operation_id="get_manual_account",
)
async def get_manual_account(
    id: int,
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> ManualAccountObject | None:
    """Fetch one synchronized manual account.

    **Parameters:**

    - **id**: Identifier of the manual account to retrieve.
    - **db**: Database manager instance.

    **Returns:** Matching account, or `None` when it has not been synchronized.
    """
    return await fetch_manual_account_by_id(db=db, account_id=id)


@router.get(
    path="/plaid_accounts/{id}",
    response_model=PlaidAccountObject | None,
    operation_id="get_plaid_account",
)
async def get_plaid_account(
    id: int,
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> PlaidAccountObject | None:
    """Fetch one synchronized Plaid account.

    **Parameters:**

    - **id**: Identifier of the Plaid account to retrieve.
    - **db**: Database manager instance.

    **Returns:** Matching account, or `None` when it has not been synchronized.
    """
    return await fetch_plaid_account_by_id(db=db, account_id=id)


@router.post(
    path="/manual_accounts",
    response_model=ManualAccountObject,
    operation_id="create_manual_account",
)
async def create_manual_account(
    request: ManualAccountCreateRequest,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> ManualAccountObject:
    """Create a manual account and store Lunch Money's canonical response."""
    return await create_manual_account_service(client=client, db=db, request=request)


@router.put(
    path="/manual_accounts/{id}",
    response_model=ManualAccountObject,
    operation_id="update_manual_account",
)
async def update_manual_account(
    id: int,
    request: ManualAccountUpdateRequest,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> ManualAccountObject:
    """Update a manual account and store Lunch Money's canonical response."""
    return await update_manual_account_service(
        client=client,
        db=db,
        account_id=id,
        request=request,
    )


@router.delete(
    path="/manual_accounts/{id}",
    status_code=204,
    operation_id="delete_manual_account",
)
async def delete_manual_account(
    id: int,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    delete_items: bool | None = None,
    delete_balance_history: bool | None = None,
) -> None:
    """Delete a manual account upstream and then remove its cached row."""
    await delete_manual_account_service(
        client=client,
        db=db,
        account_id=id,
        delete_items=delete_items,
        delete_balance_history=delete_balance_history,
    )


@router.post(
    path="/plaid_accounts/fetch",
    status_code=204,
    operation_id="trigger_plaid_fetch",
)
async def trigger_plaid_fetch(
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    id: int | None = None,
) -> None:
    """Trigger a Lunch Money transaction fetch for eligible Plaid accounts."""
    await trigger_plaid_fetch_service(
        client=client,
        start_date=start_date,
        end_date=end_date,
        account_id=id,
    )
