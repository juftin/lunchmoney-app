"""Mode-specific, database-free or stateful operation lifecycles."""

import logging
from collections.abc import AsyncIterator, Awaitable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import ClassVar, Literal, Protocol, TypeVar

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.services.adapters.accounts import (
    AccountAdapter,
    EphemeralAccountAdapter,
    StatefulAccountAdapter,
)
from lunchmoney_app.services.adapters.base import OperationMemo
from lunchmoney_app.services.adapters.budgets import (
    BudgetAdapter,
    EphemeralBudgetAdapter,
    StatefulBudgetAdapter,
)
from lunchmoney_app.services.adapters.categories import (
    CategoryAdapter,
    EphemeralCategoryAdapter,
    StatefulCategoryAdapter,
)
from lunchmoney_app.services.adapters.recurring import (
    EphemeralRecurringAdapter,
    RecurringAdapter,
    StatefulRecurringAdapter,
)
from lunchmoney_app.services.adapters.summary import (
    EphemeralSummaryReader,
    StatefulSummaryReader,
    SummaryReader,
)
from lunchmoney_app.services.adapters.tags import (
    EphemeralTagAdapter,
    StatefulTagAdapter,
    TagAdapter,
)
from lunchmoney_app.services.adapters.transactions import (
    EphemeralTransactionAdapter,
    StatefulTransactionAdapter,
    TransactionAdapter,
)
from lunchmoney_app.services.adapters.user import (
    EphemeralUserReader,
    StatefulUserReader,
    UserReader,
)
from lunchmoney_app.services.errors import StatefulModeRequired

logger = logging.getLogger(__name__)
ResultT = TypeVar("ResultT")
ContextT_co = TypeVar("ContextT_co", bound="OperationContext", covariant=True)
PROJECTION_DOMAINS: tuple[str, ...] = (
    "accounts",
    "budgets",
    "categories",
    "tags",
    "transactions",
)
"""Stateful cache domains whose mutation projection health is tracked."""

_unpersisted_stale_domains: set[str] = set()
"""Projection failures whose durable stale marker could not be written."""


class OperationContextFactory(Protocol[ContextT_co]):
    """Create and clean up one immutable operation context."""

    def operation(self) -> AbstractAsyncContextManager[ContextT_co]:
        """Return an asynchronous context manager for one operation."""
        ...


@dataclass(slots=True)
class _OperationLease:
    """Revoke collaborators shared with tasks copied from an operation context."""

    active: bool = True
    """Whether the owning operation is still active."""

    def ensure_active(self) -> None:
        """Reject access after the owning operation has exited."""
        if not self.active:
            msg = "The data operation context is no longer active"
            raise RuntimeError(msg)

    def close(self) -> None:
        """Permanently revoke this operation lease."""
        self.active = False


@dataclass(frozen=True, slots=True)
class OperationContext:
    """Immutable collaborators selected for one REST or MCP operation."""

    _guarded_attributes: ClassVar[frozenset[str]] = frozenset(
        {
            "accounts",
            "budgets",
            "categories",
            "client",
            "database",
            "memo",
            "project",
            "recurring",
            "summary",
            "tags",
            "transactions",
            "user",
        }
    )

    mode: Literal["stateful", "ephemeral"]
    _lease: _OperationLease
    client: LunchMoneyApp
    memo: OperationMemo
    user: UserReader
    accounts: AccountAdapter
    categories: CategoryAdapter
    tags: TagAdapter
    budgets: BudgetAdapter
    summary: SummaryReader
    recurring: RecurringAdapter
    transactions: TransactionAdapter

    def __getattribute__(self, name: str) -> object:
        """Reject collaborator access after operation teardown."""
        if name in type(self)._guarded_attributes:
            lease = object.__getattribute__(self, "_lease")
            lease.ensure_active()
        return object.__getattribute__(self, name)

    def ensure_active(self) -> None:
        """Reject use by work that outlived this operation."""
        self._lease.ensure_active()

    async def project(
        self,
        domain: str,
        projection: Awaitable[ResultT],
    ) -> ResultT | None:
        """Apply a projection without obscuring an authoritative upstream success."""
        self.ensure_active()
        try:
            result = await projection
        except Exception:
            logger.exception("Unable to project upstream %s mutation", domain)
            return None
        return result


@dataclass(frozen=True, slots=True)
class StatefulOperationContext(OperationContext):
    """Operation collaborators with guaranteed durable stateful storage."""

    database: LunchMoneyDatabase
    """Database selected by the stateful operation factory."""

    async def project(
        self,
        domain: str,
        projection: Awaitable[ResultT],
    ) -> ResultT | None:
        """Project an upstream mutation and track cache health failures."""
        self.ensure_active()
        try:
            result = await projection
        except Exception:
            logger.exception("Unable to project upstream %s mutation", domain)
            try:
                await self.database.upsert_cached_response(
                    f"health:stale:{domain}", {"stale": True}
                )
            except Exception:
                _unpersisted_stale_domains.add(domain)
                logger.exception("Unable to persist stale cache marker for %s", domain)
            else:
                _unpersisted_stale_domains.discard(domain)
            return None
        try:
            await self.database.delete_cached_responses(f"health:stale:{domain}")
        except Exception:
            logger.exception("Unable to clear stale cache marker for %s", domain)
        else:
            _unpersisted_stale_domains.discard(domain)
        return result


_operation_context: ContextVar[OperationContext | None] = ContextVar(
    "operation_context", default=None
)


def get_operation_context() -> OperationContext:
    """Return the bound operation context or fail without resolving storage."""
    context = _operation_context.get()
    if context is None:
        msg = "No data operation is bound to the current execution context"
        raise RuntimeError(msg)
    context.ensure_active()
    return context


def get_stateful_operation_context() -> StatefulOperationContext:
    """Return the bound stateful context or raise the shared mode boundary."""
    context = get_operation_context()
    if not isinstance(context, StatefulOperationContext):
        raise StatefulModeRequired
    return context


def get_unpersisted_stale_domains() -> frozenset[str]:
    """Return process-local stale domains whose durable marker write failed."""
    return frozenset(_unpersisted_stale_domains)


def clear_unpersisted_stale_domains() -> None:
    """Clear process-local projection failures after a successful full sync."""
    _unpersisted_stale_domains.clear()


async def persist_unpersisted_stale_domains(database: LunchMoneyDatabase) -> None:
    """Promote process-local stale failures to durable markers after recovery."""
    for domain in tuple(_unpersisted_stale_domains):
        try:
            await database.upsert_cached_response(
                f"health:stale:{domain}", {"stale": True}
            )
        except Exception:
            logger.exception("Unable to persist stale cache marker for %s", domain)
        else:
            _unpersisted_stale_domains.discard(domain)


class StatefulOperationContextFactory:
    """Build operation collaborators around durable synchronized storage."""

    def __init__(self, client: LunchMoneyApp, database: LunchMoneyDatabase) -> None:
        """Bind shared upstream and database dependencies."""
        self._client = client
        self._database = database

    @asynccontextmanager
    async def operation(self) -> AsyncIterator[StatefulOperationContext]:
        """Bind one stateful context for the complete operation."""
        memo = OperationMemo()
        categories = StatefulCategoryAdapter(self._database, memo)
        context = StatefulOperationContext(
            mode="stateful",
            _lease=_OperationLease(),
            client=self._client,
            memo=memo,
            user=StatefulUserReader(self._database, memo),
            accounts=StatefulAccountAdapter(self._database, memo),
            categories=categories,
            tags=StatefulTagAdapter(self._database, memo),
            budgets=StatefulBudgetAdapter(self._database, self._client, memo),
            summary=StatefulSummaryReader(self._database, self._client, memo),
            recurring=StatefulRecurringAdapter(self._database, self._client, memo),
            transactions=StatefulTransactionAdapter(self._database, memo),
            database=self._database,
        )
        async with _bind_context(context):
            yield context


class EphemeralOperationContextFactory:
    """Build live collaborators without constructing any database object."""

    def __init__(self, client: LunchMoneyApp) -> None:
        """Bind the shared non-retaining upstream client."""
        self._client = client

    @asynccontextmanager
    async def operation(self) -> AsyncIterator[OperationContext]:
        """Bind one database-free context for the complete operation."""
        memo = OperationMemo()
        categories = EphemeralCategoryAdapter(self._client, memo)
        context = OperationContext(
            mode="ephemeral",
            _lease=_OperationLease(),
            client=self._client,
            memo=memo,
            user=EphemeralUserReader(self._client, memo),
            accounts=EphemeralAccountAdapter(self._client, memo),
            categories=categories,
            tags=EphemeralTagAdapter(self._client, memo),
            budgets=EphemeralBudgetAdapter(self._client, memo),
            summary=EphemeralSummaryReader(self._client, categories, memo),
            recurring=EphemeralRecurringAdapter(self._client, memo),
            transactions=EphemeralTransactionAdapter(self._client, memo),
        )
        async with _bind_context(context):
            yield context


@asynccontextmanager
async def _bind_context(context: OperationContext) -> AsyncIterator[None]:
    """Bind and unconditionally reset one operation context."""
    token: Token[OperationContext | None] = _operation_context.set(context)
    try:
        yield
    finally:
        try:
            context.memo.clear()
        finally:
            context._lease.close()
            _operation_context.reset(token)


__all__ = [
    "EphemeralOperationContextFactory",
    "OperationContext",
    "OperationContextFactory",
    "PROJECTION_DOMAINS",
    "StatefulOperationContext",
    "StatefulOperationContextFactory",
    "clear_unpersisted_stale_domains",
    "get_operation_context",
    "get_unpersisted_stale_domains",
    "get_stateful_operation_context",
    "persist_unpersisted_stale_domains",
]
