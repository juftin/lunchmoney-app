"""Stateful and live user readers."""

from typing import Protocol

from lunchmoney.models import UserObject
from sqlmodel import select

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import User
from lunchmoney_app.services.adapters.base import OperationMemo


class UserReader(Protocol):
    """Read the authenticated Lunch Money user."""

    async def get(self) -> UserObject | None:
        """Return the current user when available."""
        ...


class StatefulUserReader:
    """Read the user from synchronized storage."""

    def __init__(self, database: LunchMoneyDatabase, memo: OperationMemo) -> None:
        """Bind synchronized storage and an operation memo."""
        self._database = database
        self._memo = memo

    async def get(self) -> UserObject | None:
        """Return the synchronized user profile."""

        async def load() -> UserObject | None:
            async with self._database.session() as session:
                result = await session.exec(select(User))
                record = result.first()
                return record.to_api() if record is not None else None

        return await self._memo.get_or_create(("user",), load)


class EphemeralUserReader:
    """Read the user directly from Lunch Money."""

    def __init__(self, client: LunchMoneyApp, memo: OperationMemo) -> None:
        """Bind the non-retaining upstream client and operation memo."""
        self._client = client
        self._memo = memo

    async def get(self) -> UserObject:
        """Return the live authenticated user."""
        return await self._memo.get_or_create(("user",), self._client.client.me.get_me)


__all__ = ["EphemeralUserReader", "StatefulUserReader", "UserReader"]
