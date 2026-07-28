"""Accounts data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import ManualAccount, PlaidAccount
from lunchmoney_mcp.schemas import AccountInfo, AccountsSummary

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
    plaid_accs = await db.list(PlaidAccount)
    manual_accs = await db.list(ManualAccount)
    return AccountsSummary(
        plaid_accounts=[
            AccountInfo(
                id=a.id,
                name=a.name,
                institution_name=a.institution_name,
                balance=float(a.balance),
                currency=a.currency,
                type_or_status=a.status,
            )
            for a in plaid_accs
        ],
        manual_accounts=[
            AccountInfo(
                id=a.id,
                name=a.name,
                balance=float(a.balance),
                currency=a.currency,
                type_or_status=a.type,
            )
            for a in manual_accs
        ],
    )
