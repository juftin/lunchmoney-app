"""Stateful and live account readers and projectors."""

import asyncio
import builtins
from typing import Protocol

from lunchmoney.models import ManualAccountObject, PlaidAccountObject

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import ManualAccount, PlaidAccount, Transaction
from lunchmoney_app.schemas import AccountsSummary
from lunchmoney_app.services.adapters.base import OperationMemo


class AccountAdapter(Protocol):
    """Read and project account-domain values."""

    async def list(self) -> AccountsSummary: ...
    async def list_manual(self) -> builtins.list[ManualAccountObject]: ...
    async def list_plaid(self) -> builtins.list[PlaidAccountObject]: ...
    async def get_manual(self, account_id: int) -> ManualAccountObject | None: ...
    async def get_plaid(self, account_id: int) -> PlaidAccountObject | None: ...
    async def store_manual(self, account: ManualAccountObject) -> None: ...
    async def delete_manual(self, account_id: int, delete_items: bool) -> None: ...
    async def invalidate_after_plaid_fetch(self) -> None: ...
    def invalidate(self, transactions: bool = False) -> None: ...


class StatefulAccountAdapter:
    """Serve accounts from and project writes into synchronized storage."""

    def __init__(self, database: LunchMoneyDatabase, memo: OperationMemo) -> None:
        """Bind synchronized storage and operation-local memoization."""
        self._database = database
        self._memo = memo

    async def list(self) -> AccountsSummary:
        """Return both synchronized account collections."""
        manual, plaid = await asyncio.gather(self.list_manual(), self.list_plaid())
        return AccountsSummary(manual_accounts=manual, plaid_accounts=plaid)

    async def list_manual(self) -> builtins.list[ManualAccountObject]:
        """Return all synchronized manual accounts."""
        return await self._memo.get_or_create(
            ("accounts:manual",),
            self._load_manual,
        )

    async def _load_manual(self) -> builtins.list[ManualAccountObject]:
        """Load manual accounts from storage."""
        return [item.to_api() for item in await self._database.list(ManualAccount)]

    async def list_plaid(self) -> builtins.list[PlaidAccountObject]:
        """Return all synchronized Plaid accounts."""
        return await self._memo.get_or_create(("accounts:plaid",), self._load_plaid)

    async def _load_plaid(self) -> builtins.list[PlaidAccountObject]:
        """Load Plaid accounts from storage."""
        return [item.to_api() for item in await self._database.list(PlaidAccount)]

    async def get_manual(self, account_id: int) -> ManualAccountObject | None:
        """Return one synchronized manual account."""

        async def load() -> ManualAccountObject | None:
            item = await self._database.get(ManualAccount, account_id)
            return item.to_api() if item is not None else None

        return await self._memo.get_or_create(
            ("accounts:manual:detail", account_id), load
        )

    async def get_plaid(self, account_id: int) -> PlaidAccountObject | None:
        """Return one synchronized Plaid account."""

        async def load() -> PlaidAccountObject | None:
            item = await self._database.get(PlaidAccount, account_id)
            return item.to_api() if item is not None else None

        return await self._memo.get_or_create(
            ("accounts:plaid:detail", account_id), load
        )

    async def store_manual(self, account: ManualAccountObject) -> None:
        """Project one canonical manual account."""
        await self._database.upsert(ManualAccount.from_api(account))
        self.invalidate()

    async def delete_manual(self, account_id: int, delete_items: bool) -> None:
        """Remove a manual account and reconcile cached transaction relations."""
        transactions = await self._database.list(Transaction)
        affected = [
            item for item in transactions if item.manual_account_id == account_id
        ]
        if delete_items:
            for transaction in affected:
                await self._database.delete(Transaction, transaction.id)
        else:
            for transaction in affected:
                transaction.manual_account_id = None
            if affected:
                await self._database.upsert_many(affected)
        await self._database.delete(ManualAccount, account_id)
        if delete_items:
            await self._database.delete_cached_responses("summary:")
        self.invalidate(transactions=True)

    async def invalidate_after_plaid_fetch(self) -> None:
        """Invalidate snapshots potentially changed by newly imported transactions."""
        await self._database.delete_cached_responses("summary:")
        self.invalidate(transactions=True)

    def invalidate(self, transactions: bool = False) -> None:
        """Invalidate affected operation-local account reads."""
        prefixes = ["accounts"]
        if transactions:
            prefixes.extend(("transactions", "summary", "analytics"))
        self._memo.invalidate(*prefixes)


class EphemeralAccountAdapter:
    """Serve accounts live and retain no post-write projection."""

    def __init__(self, client: LunchMoneyApp, memo: OperationMemo) -> None:
        """Bind a non-retaining upstream client and operation memo."""
        self._client = client
        self._memo = memo

    async def list(self) -> AccountsSummary:
        """Return live manual and Plaid account collections concurrently."""
        manual, plaid = await asyncio.gather(self.list_manual(), self.list_plaid())
        return AccountsSummary(manual_accounts=manual, plaid_accounts=plaid)

    async def list_manual(self) -> builtins.list[ManualAccountObject]:
        """Return every live manual account."""

        async def load() -> builtins.list[ManualAccountObject]:
            response = (
                await self._client.client.manual_accounts.get_all_manual_accounts()
            )
            return list(response.manual_accounts or [])

        return await self._memo.get_or_create(("accounts:manual",), load)

    async def list_plaid(self) -> builtins.list[PlaidAccountObject]:
        """Return every live Plaid account."""

        async def load() -> builtins.list[PlaidAccountObject]:
            response = await self._client.client.plaid.get_all_plaid_accounts()
            return list(response.plaid_accounts or [])

        return await self._memo.get_or_create(("accounts:plaid",), load)

    async def get_manual(self, account_id: int) -> ManualAccountObject | None:
        """Return one live manual account, translating upstream not-found."""
        try:
            return await self._memo.get_or_create(
                ("accounts:manual:detail", account_id),
                lambda: self._client.client.manual_accounts.get_manual_account_by_id(
                    id=account_id
                ),
            )
        except Exception as error:
            if getattr(error, "status", None) == 404:
                return None
            raise

    async def get_plaid(self, account_id: int) -> PlaidAccountObject | None:
        """Return one live Plaid account, translating upstream not-found."""
        try:
            return await self._memo.get_or_create(
                ("accounts:plaid:detail", account_id),
                lambda: self._client.client.plaid.get_plaid_account_by_id(
                    id=account_id
                ),
            )
        except Exception as error:
            if getattr(error, "status", None) == 404:
                return None
            raise

    async def store_manual(self, account: ManualAccountObject) -> None:
        """Discard a canonical write response and invalidate operation reads."""
        del account
        self.invalidate()

    async def delete_manual(self, account_id: int, delete_items: bool) -> None:
        """Retain no deleted account state and invalidate operation reads."""
        del account_id, delete_items
        self.invalidate(transactions=True)

    async def invalidate_after_plaid_fetch(self) -> None:
        """Invalidate operation-local reads after triggering a live import."""
        self.invalidate(transactions=True)

    def invalidate(self, transactions: bool = False) -> None:
        """Invalidate affected operation-local live reads."""
        prefixes = ["accounts"]
        if transactions:
            prefixes.extend(("transactions", "summary", "analytics"))
        self._memo.invalidate(*prefixes)


__all__ = ["AccountAdapter", "EphemeralAccountAdapter", "StatefulAccountAdapter"]
