"""Accounts data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import AccountInfo, AccountsSummary
from lunchmoney_mcp.services import (
    fetch_accounts,
    fetch_manual_account_by_id,
    fetch_plaid_account_by_id,
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

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    AccountsSummary
        Combined summary of connected Plaid and manual accounts.
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

    Parameters
    ----------
    account_id : int
        Identifier of the manual account to retrieve.
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    AccountInfo | None
        Matching account, or ``None`` when it has not been synchronized.
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

    Parameters
    ----------
    account_id : int
        Identifier of the Plaid account to retrieve.
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    AccountInfo | None
        Matching account, or ``None`` when it has not been synchronized.
    """
    return await fetch_plaid_account_by_id(db=db, account_id=account_id)
