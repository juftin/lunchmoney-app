"""Stateful and live tag readers and projectors."""

from typing import Protocol

from lunchmoney.models import TagObject

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import Tag, Transaction
from lunchmoney_app.services.adapters.base import OperationMemo


class TagAdapter(Protocol):
    """Read and project tag-domain values."""

    async def list(self) -> list[TagObject]: ...
    async def get(self, tag_id: int) -> TagObject | None: ...
    async def store(self, tag: TagObject) -> None: ...
    async def delete(self, tag_id: int) -> None: ...
    def invalidate(self) -> None: ...


class StatefulTagAdapter:
    """Serve tags from and project writes into synchronized storage."""

    def __init__(self, database: LunchMoneyDatabase, memo: OperationMemo) -> None:
        """Bind synchronized storage and operation memoization."""
        self._database = database
        self._memo = memo

    async def list(self) -> list[TagObject]:
        """Return all synchronized tags."""

        async def load() -> list[TagObject]:
            return [item.to_api() for item in await self._database.list(Tag)]

        return await self._memo.get_or_create(("tags:list",), load)

    async def get(self, tag_id: int) -> TagObject | None:
        """Return one synchronized tag."""

        async def load() -> TagObject | None:
            item = await self._database.get(Tag, tag_id)
            return item.to_api() if item is not None else None

        return await self._memo.get_or_create(("tags:detail", tag_id), load)

    async def store(self, tag: TagObject) -> None:
        """Project one canonical tag."""
        await self._database.upsert(Tag.from_api(tag))
        self.invalidate()

    async def delete(self, tag_id: int) -> None:
        """Delete a tag and remove synchronized transaction links."""
        transactions = await self._database.list(Transaction)
        affected = [
            item
            for item in transactions
            if any(link.tag_id == tag_id for link in item.tag_links)
        ]
        for transaction in affected:
            transaction.tag_links = [
                link for link in transaction.tag_links if link.tag_id != tag_id
            ]
            transaction.tags = [tag for tag in transaction.tags if tag.id != tag_id]
        if affected:
            await self._database.upsert_many(affected)
        await self._database.delete(Tag, tag_id)
        self.invalidate()

    def invalidate(self) -> None:
        """Invalidate tag-dependent operation reads."""
        self._memo.invalidate("tags", "transactions")


class EphemeralTagAdapter:
    """Serve tags live and retain no projections."""

    def __init__(self, client: LunchMoneyApp, memo: OperationMemo) -> None:
        """Bind a non-retaining upstream client and operation memo."""
        self._client = client
        self._memo = memo

    async def list(self) -> list[TagObject]:
        """Return every live tag."""

        async def load() -> list[TagObject]:
            response = await self._client.client.tags.get_all_tags()
            return list(response.tags or [])

        return await self._memo.get_or_create(("tags:list",), load)

    async def get(self, tag_id: int) -> TagObject | None:
        """Return one live tag, translating upstream not-found."""
        try:
            return await self._memo.get_or_create(
                ("tags:detail", tag_id),
                lambda: self._client.client.tags.get_tag_by_id(id=tag_id),
            )
        except Exception as error:
            if getattr(error, "status", None) == 404:
                return None
            raise

    async def store(self, tag: TagObject) -> None:
        """Discard a write projection and invalidate operation reads."""
        del tag
        self.invalidate()

    async def delete(self, tag_id: int) -> None:
        """Retain no deletion projection and invalidate operation reads."""
        del tag_id
        self.invalidate()

    def invalidate(self) -> None:
        """Invalidate tag-dependent operation reads."""
        self._memo.invalidate("tags", "transactions")


__all__ = ["EphemeralTagAdapter", "StatefulTagAdapter", "TagAdapter"]
