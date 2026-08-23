"""Stateful and live recurring-item readers."""

import datetime
from dataclasses import dataclass
from typing import Protocol

from lunchmoney.models import RecurringObject

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import RecurringItem
from lunchmoney_app.services.adapters.base import OperationMemo


@dataclass(frozen=True, slots=True)
class RecurringQuery:
    """Query controls for a recurring-item collection."""

    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    include_suggested: bool | None = None


class RecurringAdapter(Protocol):
    """Read recurring items and details."""

    async def list(self, query: RecurringQuery) -> list[RecurringObject]: ...
    async def get(
        self,
        recurring_item_id: int,
        start_date: datetime.date | None,
        end_date: datetime.date | None,
    ) -> RecurringObject: ...


def _filter_suggested(
    items: list[RecurringObject], include_suggested: bool | None
) -> list[RecurringObject]:
    """Apply the public suggested-item default."""
    if include_suggested is True:
        return items
    return [item for item in items if item.status != "suggested"]


class StatefulRecurringAdapter:
    """Read recurring response snapshots from synchronized storage."""

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

    async def list(self, query: RecurringQuery) -> list[RecurringObject]:
        """Return recurring items from a keyed durable snapshot."""

        async def load() -> list[RecurringObject]:
            key = (
                f"recurring:{query.start_date}:{query.end_date}"
                if query.start_date is not None or query.end_date is not None
                else "recurring:latest"
            )
            payload = await self._database.get_cached_response(key)
            if payload is None:
                response = await self._client.client.recurring_items.get_all_recurring(
                    start_date=query.start_date,
                    end_date=query.end_date,
                    include_suggested=True,
                )
                payload = {
                    "items": [
                        item.model_dump(mode="json")
                        for item in response.recurring_items or []
                    ]
                }
                await self._database.upsert_cached_response(key, payload)
            items = [RecurringObject.model_validate(item) for item in payload["items"]]
            return _filter_suggested(items, query.include_suggested)

        return await self._memo.get_or_create(("recurring:list", query), load)

    async def get(
        self,
        recurring_item_id: int,
        start_date: datetime.date | None,
        end_date: datetime.date | None,
    ) -> RecurringObject:
        """Return a cached undated detail or fetch and persist it."""

        async def load() -> RecurringObject:
            if start_date is None and end_date is None:
                cached = await self._database.get(RecurringItem, recurring_item_id)
                if cached is not None:
                    return RecurringObject.model_validate(cached.payload)
            item = await self._client.client.recurring_items.get_recurring_by_id(
                id=recurring_item_id,
                start_date=start_date,
                end_date=end_date,
            )
            if start_date is None and end_date is None:
                await self._database.upsert(
                    RecurringItem(id=item.id, payload=item.model_dump(mode="json"))
                )
            return item

        return await self._memo.get_or_create(
            ("recurring:detail", recurring_item_id, start_date, end_date), load
        )


class EphemeralRecurringAdapter:
    """Read recurring items live without retaining snapshots."""

    def __init__(self, client: LunchMoneyApp, memo: OperationMemo) -> None:
        """Bind a non-retaining upstream client and operation memo."""
        self._client = client
        self._memo = memo

    async def list(self, query: RecurringQuery) -> list[RecurringObject]:
        """Return current recurring items for a complete query."""

        async def load() -> list[RecurringObject]:
            response = await self._client.client.recurring_items.get_all_recurring(
                start_date=query.start_date,
                end_date=query.end_date,
                include_suggested=True,
            )
            return _filter_suggested(
                list(response.recurring_items or []), query.include_suggested
            )

        return await self._memo.get_or_create(("recurring:list", query), load)

    async def get(
        self,
        recurring_item_id: int,
        start_date: datetime.date | None,
        end_date: datetime.date | None,
    ) -> RecurringObject:
        """Return one current recurring item."""
        return await self._memo.get_or_create(
            ("recurring:detail", recurring_item_id, start_date, end_date),
            lambda: self._client.client.recurring_items.get_recurring_by_id(
                id=recurring_item_id,
                start_date=start_date,
                end_date=end_date,
            ),
        )


__all__ = [
    "EphemeralRecurringAdapter",
    "RecurringAdapter",
    "RecurringQuery",
    "StatefulRecurringAdapter",
]
