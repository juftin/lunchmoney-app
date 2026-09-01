"""Stateful and live budget adapters."""

from typing import Protocol

from lunchmoney.models import BudgetSettingsResponseObject

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.services.adapters.base import OperationMemo


class BudgetAdapter(Protocol):
    """Read budget settings and invalidate derived views."""

    async def get_settings(self) -> BudgetSettingsResponseObject: ...
    async def invalidate(self) -> None: ...


class StatefulBudgetAdapter:
    """Read and cache budget settings in durable storage."""

    def __init__(
        self,
        database: LunchMoneyDatabase,
        client: LunchMoneyApp,
        memo: OperationMemo,
    ) -> None:
        """Bind storage, the upstream client, and operation memoization."""
        self._database = database
        self._client = client
        self._memo = memo

    async def get_settings(self) -> BudgetSettingsResponseObject:
        """Return cached settings, populating the snapshot on miss."""

        async def load() -> BudgetSettingsResponseObject:
            payload = await self._database.get_cached_response("budget-settings")
            if payload is not None:
                return BudgetSettingsResponseObject.model_validate(payload)
            value = await self._client.client.budgets.get_budget_settings()
            await self._database.upsert_cached_response(
                "budget-settings", value.model_dump(mode="json")
            )
            return value

        return await self._memo.get_or_create(("budgets:settings",), load)

    async def invalidate(self) -> None:
        """Invalidate durable and operation-local budget-derived snapshots."""
        await self._database.delete_cached_responses("summary:")
        self._memo.invalidate("budgets", "summary", "analytics")


class EphemeralBudgetAdapter:
    """Read budget settings live without retaining snapshots."""

    def __init__(self, client: LunchMoneyApp, memo: OperationMemo) -> None:
        """Bind a non-retaining upstream client and operation memo."""
        self._client = client
        self._memo = memo

    async def get_settings(self) -> BudgetSettingsResponseObject:
        """Return current upstream budget settings."""
        return await self._memo.get_or_create(
            ("budgets:settings",), self._client.client.budgets.get_budget_settings
        )

    async def invalidate(self) -> None:
        """Invalidate operation-local budget-derived reads."""
        self._memo.invalidate("budgets", "summary", "analytics")


__all__ = ["BudgetAdapter", "EphemeralBudgetAdapter", "StatefulBudgetAdapter"]
