"""Accounts data endpoints."""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
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
    """List all connected Plaid and manual accounts with current balances.

    **Parameters:**

    - **db**: Database manager instance.

    **Returns:** Combined summary of connected Plaid and manual accounts.
    """
    return await fetch_accounts(db=db)


@router.get(
    path="/accounts/manual/{account_id}",
    response_model=AccountInfo | None,
    operation_id="get_manual_account",
)
async def get_manual_account(
    account_id: int,
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> AccountInfo | None:
    """Fetch one synchronized manual account.

    **Parameters:**

    - **account_id**: Identifier of the manual account to retrieve.
    - **db**: Database manager instance.

    **Returns:** Matching account, or `None` when it has not been synchronized.
    """
    return await fetch_manual_account_by_id(db=db, account_id=account_id)


@router.get(
    path="/accounts/plaid/{account_id}",
    response_model=AccountInfo | None,
    operation_id="get_plaid_account",
)
async def get_plaid_account(
    account_id: int,
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> AccountInfo | None:
    """Fetch one synchronized Plaid account.

    **Parameters:**

    - **account_id**: Identifier of the Plaid account to retrieve.
    - **db**: Database manager instance.

    **Returns:** Matching account, or `None` when it has not been synchronized.
    """
    return await fetch_plaid_account_by_id(db=db, account_id=account_id)


@router.post(
    path="/accounts/manual",
    response_model=AccountInfo,
    operation_id="create_manual_account",
)
async def create_manual_account(
    request: ManualAccountCreateRequest,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> AccountInfo:
    """Create a manual account and store Lunch Money's canonical response."""
    return await create_manual_account_service(client=client, db=db, request=request)


@router.put(
    path="/accounts/manual/{account_id}",
    response_model=AccountInfo,
    operation_id="update_manual_account",
)
async def update_manual_account(
    account_id: int,
    request: ManualAccountUpdateRequest,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> AccountInfo:
    """Update a manual account and store Lunch Money's canonical response."""
    return await update_manual_account_service(
        client=client,
        db=db,
        account_id=account_id,
        request=request,
    )


@router.delete(
    path="/accounts/manual/{account_id}",
    status_code=204,
    operation_id="delete_manual_account",
)
async def delete_manual_account(
    account_id: int,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    delete_items: bool | None = None,
    delete_balance_history: bool | None = None,
) -> None:
    """Delete a manual account upstream and then remove its cached row."""
    await delete_manual_account_service(
        client=client,
        db=db,
        account_id=account_id,
        delete_items=delete_items,
        delete_balance_history=delete_balance_history,
    )


@router.post(
    path="/accounts/plaid/sync",
    status_code=204,
    operation_id="trigger_plaid_fetch",
)
async def trigger_plaid_fetch(
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    account_id: int | None = None,
) -> None:
    """Trigger a Lunch Money transaction fetch for eligible Plaid accounts."""
    await trigger_plaid_fetch_service(
        client=client,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
    )
