"""Stateful and live budget-summary readers."""

import datetime
from dataclasses import dataclass
from typing import Protocol

from lunchmoney.models import CategoryObject, SummaryResponseObject

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import Category
from lunchmoney_app.schemas import CategoryQuery
from lunchmoney_app.services.adapters.base import OperationMemo
from lunchmoney_app.services.adapters.categories import CategoryAdapter


@dataclass(frozen=True, slots=True)
class SummaryQuery:
    """Complete query controlling one public summary response."""

    start_date: datetime.date
    end_date: datetime.date
    include_exclude_from_budgets: bool | None = None
    include_occurrences: bool | None = None
    include_past_budget_dates: bool | None = None
    include_totals: bool | None = None
    include_rollover_pool: bool | None = None


class SummaryReader(Protocol):
    """Read a canonical budget summary."""

    async def get(self, query: SummaryQuery) -> SummaryResponseObject: ...


def _shape_summary(
    summary: SummaryResponseObject,
    excluded_category_ids: set[int],
    query: SummaryQuery,
) -> SummaryResponseObject:
    """Apply public response controls to a complete upstream snapshot."""
    rows = summary.categories
    if query.include_exclude_from_budgets is not True:
        rows = [row for row in rows if row.category_id not in excluded_category_ids]
    if query.include_occurrences is not True:
        rows = [row.model_copy(update={"occurrences": None}) for row in rows]
    elif query.include_past_budget_dates is not True:
        rows = [
            row.model_copy(
                update={
                    "occurrences": [
                        occurrence
                        for occurrence in row.occurrences or []
                        if occurrence.in_range
                    ]
                }
            )
            for row in rows
        ]
    return summary.model_copy(
        update={
            "categories": rows,
            "totals": summary.totals if query.include_totals else None,
            "rollover_pool": (
                summary.rollover_pool if query.include_rollover_pool else None
            ),
        }
    )


class StatefulSummaryReader:
    """Read durable summary snapshots, populating them on cache miss."""

    def __init__(
        self,
        database: LunchMoneyDatabase,
        client: LunchMoneyApp,
        memo: OperationMemo,
    ) -> None:
        """Bind storage, upstream access, and operation memoization."""
        self._database = database
        self._client = client
        self._memo = memo

    async def get(self, query: SummaryQuery) -> SummaryResponseObject:
        """Return a shaped synchronized summary."""

        async def load() -> SummaryResponseObject:
            key = f"summary:{query.start_date}:{query.end_date}"
            payload = await self._database.get_cached_response(key)
            if payload is None:
                value = await _load_complete_summary(self._client, query)
                if query.include_exclude_from_budgets is not True:
                    category_objects = await self._client.refresh(
                        model=CategoryObject, cache=False
                    )
                    await self._database.upsert_many(
                        [Category.from_api(item) for item in category_objects.values()]
                    )
                payload = value.model_dump(mode="json")
                await self._database.upsert_cached_response(key, payload)
            value = SummaryResponseObject.model_validate(payload)
            excluded: set[int] = set()
            if query.include_exclude_from_budgets is not True:
                categories = await self._database.list(Category)
                excluded = {item.id for item in categories if item.exclude_from_budget}
            return _shape_summary(value, excluded, query)

        return await self._memo.get_or_create(("summary", query), load)


class EphemeralSummaryReader:
    """Read and shape a live summary without persistent snapshots."""

    def __init__(
        self,
        client: LunchMoneyApp,
        categories: CategoryAdapter,
        memo: OperationMemo,
    ) -> None:
        """Bind live sources and operation memoization."""
        self._client = client
        self._categories = categories
        self._memo = memo

    async def get(self, query: SummaryQuery) -> SummaryResponseObject:
        """Return a shaped current upstream summary."""

        async def load() -> SummaryResponseObject:
            value = await _load_complete_summary(self._client, query)
            excluded: set[int] = set()
            if query.include_exclude_from_budgets is not True:
                categories = await self._categories.list(
                    CategoryQuery(format="flattened")
                )
                excluded = {item.id for item in categories if item.exclude_from_budget}
            return _shape_summary(value, excluded, query)

        return await self._memo.get_or_create(("summary", query), load)


async def _load_complete_summary(
    client: LunchMoneyApp,
    query: SummaryQuery,
) -> SummaryResponseObject:
    """Fetch the complete upstream snapshot used for deterministic shaping."""
    return await client.client.summary.get_budget_summary(
        start_date=query.start_date,
        end_date=query.end_date,
        include_exclude_from_budgets=True,
        include_occurrences=True,
        include_past_budget_dates=True,
        include_totals=True,
        include_rollover_pool=True,
    )


__all__ = [
    "EphemeralSummaryReader",
    "StatefulSummaryReader",
    "SummaryQuery",
    "SummaryReader",
]
