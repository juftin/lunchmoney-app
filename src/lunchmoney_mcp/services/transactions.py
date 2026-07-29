"""Service logic for Transactions data operations."""

from sqlalchemy.engine.result import ScalarResult
from typing import Sequence
from sqlmodel.sql._expression_select_cls import SelectOfScalar

import datetime

from sqlmodel import col, select

from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Transaction
from lunchmoney_mcp.schemas import TransactionInfo


async def fetch_recent_transactions(
    db: LunchMoneyDatabase, days: int = 30, limit: int = 50
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
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    async with db.session() as session:
        statement: SelectOfScalar[Transaction] = (
            select(Transaction)
            .where(Transaction.var_date >= cutoff)
            .order_by(col(Transaction.var_date).desc())
            .limit(limit)
        )
        results: ScalarResult[Transaction] = await session.exec(statement)
        txns: Sequence[Transaction] = results.all()
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
