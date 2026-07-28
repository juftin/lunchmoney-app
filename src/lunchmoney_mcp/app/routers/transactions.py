"""Transactions data endpoints."""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import col, select

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Transaction
from lunchmoney_mcp.schemas import TransactionInfo

router = APIRouter(tags=["Transactions"])


@router.get(path="/transactions", response_model=list[TransactionInfo])
async def get_recent_transactions(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    days: int = 30,
    limit: int = 50,
) -> list[TransactionInfo]:
    """Fetch recent transactions from local database within specified date window."""
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    async with db.session() as session:
        statement = (
            select(Transaction)
            .where(Transaction.var_date >= cutoff)
            .order_by(col(Transaction.var_date).desc())
            .limit(limit)
        )
        results = await session.exec(statement)
        txns = results.all()
        return [
            TransactionInfo(
                id=t.id,
                date=t.var_date,
                payee=t.payee,
                amount=float(t.amount),
                currency=t.currency,
                category_id=t.category_id,
                notes=t.notes,
                status=t.status,
            )
            for t in txns
        ]
