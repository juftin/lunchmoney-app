"""Pure category spending aggregation over mode-selected canonical sources."""

import datetime
from decimal import Decimal
from typing import Literal, cast

from lunchmoney.models import CategoryObject, TransactionObject

from lunchmoney_app.schemas import (
    CategoryQuery,
    CategorySpending,
    ChildCategorySpending,
    GroupedSpendingResponse,
    SpendingTrendPoint,
    SpendingTrendsResponse,
    TransactionQuery,
)
from lunchmoney_app.services.operations import OperationContext

TrendGranularity = Literal["daily", "weekly", "monthly"]
"""Supported calendar intervals for spending trend aggregation."""


def _trend_bucket_start(
    value: datetime.date, granularity: TrendGranularity
) -> datetime.date:
    """Return the calendar start date for a requested trend granularity."""
    if granularity == "daily":
        return value
    if granularity == "weekly":
        return value - datetime.timedelta(days=value.weekday())
    return value.replace(day=1)


def _resolve_period(
    start_date: datetime.date | None,
    end_date: datetime.date | None,
    days: int | None,
) -> tuple[datetime.date, datetime.date]:
    """Resolve the inclusive analytics period."""
    resolved_end = end_date or datetime.date.today()
    resolved_start = start_date or resolved_end - datetime.timedelta(
        days=days if days is not None else 30
    )
    return resolved_start, resolved_end


async def _load_sources(
    context: OperationContext,
    start_date: datetime.date,
    end_date: datetime.date,
) -> tuple[list[CategoryObject], list[TransactionObject]]:
    """Load canonical categories and bounded transactions for aggregation."""
    categories = await context.categories.list(CategoryQuery(format="flattened"))
    transactions = await context.transactions.list(
        TransactionQuery(
            start_date=start_date,
            end_date=end_date,
            include_pending=True,
            include_split_parents=False,
        )
    )
    return categories, transactions


async def fetch_category_spending(
    context: OperationContext,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    days: int | None = 30,
) -> GroupedSpendingResponse:
    """Calculate category-grouped spending with parent/child rollups."""
    resolved_start, resolved_end = _resolve_period(start_date, end_date, days)
    categories, transactions = await _load_sources(
        context, resolved_start, resolved_end
    )
    return _aggregate_category_spending(
        categories, transactions, resolved_start, resolved_end
    )


def _aggregate_category_spending(
    categories: list[CategoryObject],
    transactions: list[TransactionObject],
    start_date: datetime.date,
    end_date: datetime.date,
) -> GroupedSpendingResponse:
    """Aggregate canonical source objects into category rollups."""
    amounts: dict[int | None, Decimal] = {}
    counts: dict[int | None, int] = {}
    for transaction in transactions:
        category_id = transaction.category_id
        amounts[category_id] = amounts.get(category_id, Decimal()) + Decimal(
            str(transaction.amount)
        )
        counts[category_id] = counts.get(category_id, 0) + 1

    parents = [item for item in categories if item.group_id is None]
    children_by_parent: dict[int, list[CategoryObject]] = {}
    for category in categories:
        if category.group_id is not None:
            children_by_parent.setdefault(category.group_id, []).append(category)

    rows: list[CategorySpending] = []
    total_spending = Decimal()
    total_income = Decimal()
    for parent in parents:
        amount = amounts.get(parent.id, Decimal())
        count = counts.get(parent.id, 0)
        children: list[ChildCategorySpending] = []
        for child in children_by_parent.get(parent.id, []):
            child_amount = amounts.get(child.id, Decimal())
            child_count = counts.get(child.id, 0)
            amount += child_amount
            count += child_count
            children.append(
                ChildCategorySpending(
                    category_id=child.id,
                    category_name=child.name,
                    is_income=child.is_income,
                    total_amount=float(child_amount),
                    transaction_count=child_count,
                )
            )
        if parent.is_income:
            total_income += amount
        else:
            total_spending += amount
        rows.append(
            CategorySpending(
                category_id=parent.id,
                category_name=parent.name,
                is_group=parent.is_group,
                is_income=parent.is_income,
                total_amount=float(amount),
                transaction_count=count,
                children=children,
            )
        )
    if None in amounts:
        uncategorized = amounts[None]
        total_spending += uncategorized
        rows.append(
            CategorySpending(
                category_id=-1,
                category_name="Uncategorized",
                is_group=False,
                is_income=False,
                total_amount=float(uncategorized),
                transaction_count=counts[None],
                children=[],
            )
        )
    return GroupedSpendingResponse(
        start_date=start_date,
        end_date=end_date,
        total_spending=float(total_spending),
        total_income=float(total_income),
        categories=rows,
    )


async def fetch_spending_trends(
    context: OperationContext,
    granularity: str = "monthly",
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    days: int | None = 30,
) -> SpendingTrendsResponse:
    """Aggregate canonical transactions into calendar time-series buckets."""
    if granularity not in {"daily", "weekly", "monthly"}:
        raise ValueError("granularity must be daily, weekly, or monthly")
    resolved_granularity = cast(TrendGranularity, granularity)
    resolved_start, resolved_end = _resolve_period(start_date, end_date, days)
    categories, transactions = await _load_sources(
        context, resolved_start, resolved_end
    )
    category_map = {item.id: item for item in categories}
    buckets: dict[datetime.date, dict[str, Decimal | int]] = {}
    for transaction in transactions:
        bucket_start = _trend_bucket_start(transaction.var_date, resolved_granularity)
        bucket = buckets.setdefault(
            bucket_start,
            {
                "total_spending": Decimal(),
                "total_income": Decimal(),
                "transaction_count": 0,
            },
        )
        category = (
            category_map.get(transaction.category_id)
            if transaction.category_id is not None
            else None
        )
        key = (
            "total_income"
            if category is not None and category.is_income
            else "total_spending"
        )
        bucket[key] += Decimal(str(transaction.amount))
        bucket["transaction_count"] += 1
    return SpendingTrendsResponse(
        start_date=resolved_start,
        end_date=resolved_end,
        granularity=resolved_granularity,
        trends=[
            SpendingTrendPoint(
                start_date=bucket_start,
                total_spending=float(bucket["total_spending"]),
                total_income=float(bucket["total_income"]),
                transaction_count=int(bucket["transaction_count"]),
            )
            for bucket_start, bucket in sorted(buckets.items())
        ],
    )
