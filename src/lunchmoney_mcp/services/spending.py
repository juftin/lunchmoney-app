"""Service logic for category spending aggregation and rollup analysis."""

import datetime
from decimal import Decimal

from sqlalchemy.engine.result import ScalarResult
from sqlmodel import select

from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Category, Transaction
from lunchmoney_mcp.schemas import (
    CategorySpending,
    ChildCategorySpending,
    GroupedSpendingResponse,
)


async def fetch_category_spending(
    db: LunchMoneyDatabase,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    days: int | None = 30,
) -> GroupedSpendingResponse:
    """Calculate category-grouped spending with parent/child rollups.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    start_date : datetime.date | None
        Optional start date for filtering transactions.
    end_date : datetime.date | None
        Optional end date for filtering transactions. Default is today.
    days : int | None
        Number of past days to analyze if start_date is not specified. Default is 30.

    Returns
    -------
    GroupedSpendingResponse
        Grouped spending report with parent/child category rollups and totals.
    """
    resolved_end: datetime.date = end_date or datetime.date.today()
    if start_date is not None:
        resolved_start: datetime.date = start_date
    else:
        window_days: int = days if days is not None else 30
        resolved_start = resolved_end - datetime.timedelta(days=window_days)

    categories = await db.list(Category)

    async with db.session() as session:
        statement = select(Transaction).where(
            Transaction.var_date >= resolved_start,
            Transaction.var_date <= resolved_end,
            Transaction.is_split_parent != True,  # noqa: E712
        )
        results: ScalarResult[Transaction] = await session.exec(statement)
        transactions = list(results.all())

    cat_amounts: dict[int | None, Decimal] = {}
    cat_counts: dict[int | None, int] = {}
    for txn in transactions:
        cid = txn.category_id
        cat_amounts[cid] = cat_amounts.get(cid, Decimal(0)) + txn.amount
        cat_counts[cid] = cat_counts.get(cid, 0) + 1

    parent_categories: list[Category] = [c for c in categories if c.group_id is None]
    children_by_parent: dict[int, list[Category]] = {}
    for c in categories:
        if c.group_id is not None:
            children_by_parent.setdefault(c.group_id, []).append(c)

    spending_items: list[CategorySpending] = []
    total_spending = Decimal(0)
    total_income = Decimal(0)

    for parent in parent_categories:
        child_objs: list[Category] = children_by_parent.get(parent.id, [])
        child_spendings: list[ChildCategorySpending] = []

        parent_direct_amount = cat_amounts.get(parent.id, Decimal(0))
        parent_direct_count = cat_counts.get(parent.id, 0)

        rollup_amount = parent_direct_amount
        rollup_count = parent_direct_count

        for child in child_objs:
            c_amount = cat_amounts.get(child.id, Decimal(0))
            c_count = cat_counts.get(child.id, 0)
            rollup_amount += c_amount
            rollup_count += c_count

            child_spendings.append(
                ChildCategorySpending(
                    category_id=child.id,
                    category_name=child.name,
                    is_income=child.is_income,
                    total_amount=float(c_amount),
                    transaction_count=c_count,
                )
            )

        if parent.is_income:
            total_income += rollup_amount
        else:
            total_spending += rollup_amount

        spending_items.append(
            CategorySpending(
                category_id=parent.id,
                category_name=parent.name,
                is_group=parent.is_group,
                is_income=parent.is_income,
                total_amount=float(rollup_amount),
                transaction_count=rollup_count,
                children=child_spendings,
            )
        )

    if None in cat_amounts:
        uncat_amount = cat_amounts[None]
        uncat_count = cat_counts[None]
        total_spending += uncat_amount
        spending_items.append(
            CategorySpending(
                category_id=-1,
                category_name="Uncategorized",
                is_group=False,
                is_income=False,
                total_amount=float(uncat_amount),
                transaction_count=uncat_count,
                children=[],
            )
        )

    return GroupedSpendingResponse(
        start_date=resolved_start,
        end_date=resolved_end,
        total_spending=float(total_spending),
        total_income=float(total_income),
        categories=spending_items,
    )
