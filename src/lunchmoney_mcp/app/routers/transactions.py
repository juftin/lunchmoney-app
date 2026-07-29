"""Transactions data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import TransactionInfo
from lunchmoney_mcp.services import fetch_recent_transactions, fetch_transaction_by_id

router = APIRouter(tags=["Transactions"])
"""FastAPI APIRouter for financial transactions endpoints."""


@router.get(
    path="/transactions",
    response_model=list[TransactionInfo],
    operation_id="get_recent_transactions",
)
async def get_recent_transactions(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    days: int = 30,
    limit: int = 50,
) -> list[TransactionInfo]:
    """Fetch recent transactions from local database within specified date window.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    days : int
        Number of days back from today to include. Default is 30.
    limit : int
        Maximum number of transactions to return. Default is 50.

    Returns
    -------
    list[TransactionInfo]
        Filtered list of matching transaction objects ordered by date descending.
    """
    return await fetch_recent_transactions(db=db, days=days, limit=limit)


@router.get(
    path="/transactions/{transaction_id}",
    response_model=TransactionInfo | None,
    operation_id="get_transaction",
)
async def get_transaction(
    transaction_id: int,
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> TransactionInfo | None:
    """Fetch one synchronized transaction.

    Parameters
    ----------
    transaction_id : int
        Identifier of the transaction to retrieve.
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    TransactionInfo | None
        Matching transaction, or ``None`` when it has not been synchronized.
    """
    return await fetch_transaction_by_id(db=db, transaction_id=transaction_id)
