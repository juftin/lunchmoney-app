"""Accounts data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import AccountsSummary
from lunchmoney_mcp.services import fetch_accounts

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
