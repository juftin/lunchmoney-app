"""Stateful and live category readers and projectors."""

from typing import Protocol

from lunchmoney.models import CategoryObject, ChildCategoryObject

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import Category, CategoryKind, Transaction
from lunchmoney_app.schemas import CategoryQuery
from lunchmoney_app.services.adapters.base import OperationMemo


class CategoryAdapter(Protocol):
    """Read and project category-domain values."""

    async def list(self, query: CategoryQuery) -> list[CategoryObject]: ...
    async def get(
        self, category_id: int
    ) -> CategoryObject | ChildCategoryObject | None: ...
    async def store(self, category: CategoryObject) -> None: ...
    async def delete(self, category_id: int) -> None: ...
    def invalidate(self) -> None: ...


def _sort_key(category: Category) -> tuple[bool, int, str]:
    """Order cached categories like Lunch Money's collection response."""
    return (
        category.order is None,
        category.order if category.order is not None else 0,
        category.name.casefold(),
    )


def _flat(category: Category) -> CategoryObject:
    """Convert a cached row to a flat canonical category."""
    value = category.to_api()
    return CategoryObject.model_validate(
        {**value.model_dump(mode="python"), "children": None}
    )


def _nested(category: Category) -> CategoryObject:
    """Convert a cached top-level row to a nested canonical category."""
    return CategoryObject.model_validate(category.to_api().model_dump(mode="python"))


def _filter(categories: list[Category], query: CategoryQuery) -> list[CategoryObject]:
    """Apply upstream-compatible hierarchy controls to cached rows."""
    if query.is_group is True:
        rows = [
            item
            for item in categories
            if item.kind == CategoryKind.PARENT and item.is_group
        ]
        return [_nested(item) for item in sorted(rows, key=_sort_key)]
    if query.is_group is False:
        rows = [
            item
            for item in categories
            if item.kind == CategoryKind.PARENT
            and not item.is_group
            and item.group_id is None
        ]
        return [_nested(item) for item in sorted(rows, key=_sort_key)]
    if query.format == "flattened":
        return [_flat(item) for item in sorted(categories, key=_sort_key)]
    rows = [item for item in categories if item.kind == CategoryKind.PARENT]
    return [_nested(item) for item in sorted(rows, key=_sort_key)]


class StatefulCategoryAdapter:
    """Serve categories from and project writes into synchronized storage."""

    def __init__(self, database: LunchMoneyDatabase, memo: OperationMemo) -> None:
        """Bind synchronized storage and operation memoization."""
        self._database = database
        self._memo = memo

    async def list(self, query: CategoryQuery) -> list[CategoryObject]:
        """Return categories using upstream-compatible hierarchy semantics."""

        async def load() -> list[CategoryObject]:
            return _filter(await self._database.list(Category), query)

        key = ("categories:list", *sorted(query.model_dump(mode="json").items()))
        return await self._memo.get_or_create(key, load)

    async def get(
        self, category_id: int
    ) -> CategoryObject | ChildCategoryObject | None:
        """Return one synchronized category."""

        async def load() -> CategoryObject | ChildCategoryObject | None:
            item = await self._database.get(Category, category_id)
            return item.to_api() if item is not None else None

        return await self._memo.get_or_create(("categories:detail", category_id), load)

    async def store(self, category: CategoryObject) -> None:
        """Project a canonical category and invalidate summary snapshots."""
        await self._database.upsert(Category.from_api(category))
        await self._database.delete_cached_responses("summary:")
        self.invalidate()

    async def delete(self, category_id: int) -> None:
        """Delete a category and detach it from synchronized transactions."""
        transactions = await self._database.list(Transaction)
        affected = [item for item in transactions if item.category_id == category_id]
        for transaction in affected:
            transaction.category_id = None
        if affected:
            await self._database.upsert_many(affected)
        await self._database.delete(Category, category_id)
        await self._database.delete_cached_responses("summary:")
        self.invalidate()

    def invalidate(self) -> None:
        """Invalidate category-dependent operation-local reads."""
        self._memo.invalidate("categories", "transactions", "summary", "analytics")


class EphemeralCategoryAdapter:
    """Serve categories live and retain no projections."""

    def __init__(self, client: LunchMoneyApp, memo: OperationMemo) -> None:
        """Bind a non-retaining upstream client and operation memo."""
        self._client = client
        self._memo = memo

    async def list(self, query: CategoryQuery) -> list[CategoryObject]:
        """Return the complete live category representation."""

        async def load() -> list[CategoryObject]:
            response = await self._client.client.categories.get_all_categories(
                **query.model_dump(exclude_none=True)
            )
            return list(response.categories or [])

        key = ("categories:list", *sorted(query.model_dump(mode="json").items()))
        return await self._memo.get_or_create(key, load)

    async def get(
        self, category_id: int
    ) -> CategoryObject | ChildCategoryObject | None:
        """Return one live category, translating upstream not-found."""
        try:
            return await self._memo.get_or_create(
                ("categories:detail", category_id),
                lambda: self._client.client.categories.get_category_by_id(
                    id=category_id
                ),
            )
        except Exception as error:
            if getattr(error, "status", None) == 404:
                return None
            raise

    async def store(self, category: CategoryObject) -> None:
        """Discard a write projection and invalidate operation reads."""
        del category
        self.invalidate()

    async def delete(self, category_id: int) -> None:
        """Retain no deletion projection and invalidate operation reads."""
        del category_id
        self.invalidate()

    def invalidate(self) -> None:
        """Invalidate category-dependent operation-local reads."""
        self._memo.invalidate("categories", "transactions", "summary", "analytics")


__all__ = [
    "CategoryAdapter",
    "EphemeralCategoryAdapter",
    "StatefulCategoryAdapter",
]
