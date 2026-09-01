"""Stateful and live transaction readers and projectors."""

import datetime
import builtins
from typing import Protocol

from lunchmoney.models import (
    ChildTransactionObject,
    TransactionAttachmentObject,
    TransactionObject,
)
from sqlalchemy import or_
from sqlmodel import col, select

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase, eager_options
from lunchmoney_app.database.models import (
    Category,
    Tag,
    Transaction,
    TransactionAttachment,
    TransactionKind,
)
from lunchmoney_app.schemas import TransactionQuery
from lunchmoney_app.services.adapters.base import OperationMemo


class TransactionAdapter(Protocol):
    """Read and project transaction-domain values."""

    async def list(
        self, query: TransactionQuery
    ) -> builtins.list[TransactionObject]: ...
    async def get(
        self, transaction_id: int
    ) -> TransactionObject | ChildTransactionObject | None: ...
    async def recent(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        limit: int,
    ) -> builtins.list[TransactionObject]: ...
    async def store_many(
        self, transactions: builtins.list[TransactionObject]
    ) -> None: ...
    async def delete_many(self, transaction_ids: builtins.list[int]) -> None: ...
    async def group_child_ids(self, transaction_id: int) -> builtins.list[int]: ...
    async def replace_ungrouped(
        self, transaction_id: int, restored: builtins.list[TransactionObject]
    ) -> None: ...
    async def replace_unsplit(
        self, transaction_id: int, restored: TransactionObject
    ) -> None: ...
    async def store_attachment(
        self,
        transaction_id: int,
        attachment: TransactionAttachmentObject,
    ) -> None: ...
    async def delete_attachment(self, file_id: int) -> None: ...
    def invalidate(self) -> None: ...


def _normalized_datetime(value: datetime.date | datetime.datetime) -> datetime.datetime:
    """Convert a date or datetime to a comparable UTC timestamp."""
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.UTC)
        return value.astimezone(datetime.UTC)
    return datetime.datetime.combine(value, datetime.time.min, tzinfo=datetime.UTC)


def _matches_account(account_id: int | None, filter_value: int | None) -> bool:
    """Apply Lunch Money account and cash-transaction filter semantics."""
    if filter_value is None:
        return True
    if filter_value == 0:
        return account_id is None
    return account_id == filter_value


def _matches(
    transaction: TransactionObject,
    query: TransactionQuery,
    category_ids: set[int],
) -> bool:
    """Apply upstream transaction filters to one synchronized object."""
    if query.start_date is not None and transaction.var_date < query.start_date:
        return False
    if query.end_date is not None and transaction.var_date > query.end_date:
        return False
    if query.created_since is not None and _normalized_datetime(
        transaction.created_at
    ) < _normalized_datetime(query.created_since):
        return False
    if query.updated_since is not None and _normalized_datetime(
        transaction.updated_at
    ) < _normalized_datetime(query.updated_since):
        return False
    if not _matches_account(transaction.manual_account_id, query.manual_account_id):
        return False
    if not _matches_account(transaction.plaid_account_id, query.plaid_account_id):
        return False
    if (
        query.recurring_id is not None
        and transaction.recurring_id != query.recurring_id
    ):
        return False
    if query.category_id == 0 and transaction.category_id is not None:
        return False
    if (
        query.category_id not in (None, 0)
        and transaction.category_id not in category_ids
    ):
        return False
    if query.tag_id is not None and query.tag_id not in transaction.tag_ids:
        return False
    if (
        query.is_group_parent is not None
        and transaction.is_group_parent != query.is_group_parent
    ):
        return False
    if query.status is not None and transaction.status != query.status:
        return False
    if query.is_pending is not None and transaction.is_pending != query.is_pending:
        return False
    if (
        query.is_pending is None
        and query.include_pending is not True
        and transaction.is_pending
    ):
        return False
    return not (query.include_split_parents is not True and transaction.is_split_parent)


def _as_parent(transaction: Transaction) -> TransactionObject:
    """Expose a cached parent or grouped child as a collection object."""
    value = transaction.to_api()
    if isinstance(value, TransactionObject):
        return value
    return TransactionObject.model_validate(
        {**value.model_dump(mode="python"), "children": None}
    )


class StatefulTransactionAdapter:
    """Serve transactions from and project writes into synchronized storage."""

    def __init__(self, database: LunchMoneyDatabase, memo: OperationMemo) -> None:
        """Bind synchronized storage and operation memoization."""
        self._database = database
        self._memo = memo

    async def list(self, query: TransactionQuery) -> builtins.list[TransactionObject]:
        """Return synchronized transactions with upstream-compatible filtering."""

        async def load() -> builtins.list[TransactionObject]:
            category_ids: set[int] = set()
            category_id = query.category_id
            if category_id is not None and category_id != 0:
                category_ids.add(category_id)
                categories = await self._database.list(Category)
                category_ids.update(
                    item.id for item in categories if item.group_id == category_id
                )
            if query.start_date is None and query.end_date is None:
                rows = await self._database.list(Transaction)
            else:
                async with self._database.session() as session:
                    statement = select(Transaction).options(*eager_options(Transaction))
                    if query.start_date is not None:
                        statement = statement.where(
                            col(Transaction.var_date) >= query.start_date
                        )
                    if query.end_date is not None:
                        statement = statement.where(
                            col(Transaction.var_date) <= query.end_date
                        )
                    if query.include_group_children is True:
                        statement = statement.where(
                            or_(
                                col(Transaction.kind) == TransactionKind.PARENT,
                                (col(Transaction.kind) == TransactionKind.CHILD)
                                & col(Transaction.group_parent_id).is_not(None),
                            )
                        )
                    else:
                        statement = statement.where(
                            col(Transaction.kind) == TransactionKind.PARENT
                        )
                    statement = statement.order_by(
                        col(Transaction.var_date).desc(), col(Transaction.id).desc()
                    )
                    results = await session.exec(statement)
                    rows = list(results.all())
            candidates = [
                _as_parent(item)
                for item in rows
                if item.kind == TransactionKind.PARENT
                or (
                    query.include_group_children is True
                    and item.kind == TransactionKind.CHILD
                    and item.group_parent_id is not None
                )
            ]
            return sorted(
                [item for item in candidates if _matches(item, query, category_ids)],
                key=lambda item: (item.var_date, item.id),
                reverse=True,
            )

        key = ("transactions:list", *sorted(query.model_dump(mode="json").items()))
        return await self._memo.get_or_create(key, load)

    async def recent(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        limit: int,
    ) -> builtins.list[TransactionObject]:
        """Return a SQL-bounded recent parent collection for the dashboard."""

        async def load() -> builtins.list[TransactionObject]:
            async with self._database.session() as session:
                statement = (
                    select(Transaction)
                    .options(*eager_options(Transaction))
                    .where(
                        col(Transaction.var_date) >= start_date,
                        col(Transaction.var_date) <= end_date,
                        col(Transaction.kind) == TransactionKind.PARENT,
                        col(Transaction.is_split_parent).is_not(True),
                    )
                    .order_by(
                        col(Transaction.var_date).desc(), col(Transaction.id).desc()
                    )
                    .limit(limit)
                )
                results = await session.exec(statement)
                return [_as_parent(item) for item in results.all()]

        return await self._memo.get_or_create(
            ("transactions:recent", start_date, end_date, limit), load
        )

    async def get(
        self, transaction_id: int
    ) -> TransactionObject | ChildTransactionObject | None:
        """Return one synchronized transaction graph."""

        async def load() -> TransactionObject | ChildTransactionObject | None:
            item = await self._database.get(Transaction, transaction_id)
            return item.to_api() if item is not None else None

        return await self._memo.get_or_create(
            ("transactions:detail", transaction_id), load
        )

    async def store_many(self, transactions: builtins.list[TransactionObject]) -> None:
        """Project canonical transaction graphs and invalidate summaries."""
        tags = await self._database.list(Tag)
        for transaction in transactions:
            await self._database.upsert(Transaction.from_api(transaction, tags=tags))
        await self._database.delete_cached_responses("summary:")
        self.invalidate()

    async def delete_many(self, transaction_ids: builtins.list[int]) -> None:
        """Delete synchronized transaction graphs and invalidate summaries."""
        for transaction_id in transaction_ids:
            await self._database.delete(Transaction, transaction_id)
        await self._database.delete_cached_responses("summary:")
        self.invalidate()

    async def group_child_ids(self, transaction_id: int) -> builtins.list[int]:
        """Return cached child identifiers before an ungroup mutation."""
        group = await self._database.get(Transaction, transaction_id)
        return [item.id for item in group.group_children] if group is not None else []

    async def replace_ungrouped(
        self, transaction_id: int, restored: builtins.list[TransactionObject]
    ) -> None:
        """Replace a cached group with its restored children."""
        await self._database.delete(Transaction, transaction_id)
        if restored:
            await self.store_many(restored)
        else:
            await self._database.delete_cached_responses("summary:")
            self.invalidate()

    async def replace_unsplit(
        self, transaction_id: int, restored: TransactionObject
    ) -> None:
        """Replace a cached split graph with its restored parent."""
        await self._database.delete(Transaction, transaction_id)
        await self.store_many([restored])

    async def store_attachment(
        self,
        transaction_id: int,
        attachment: TransactionAttachmentObject,
    ) -> None:
        """Append canonical attachment metadata to a known cached transaction."""
        transaction = await self._database.get(Transaction, transaction_id)
        if transaction is not None:
            transaction.attachments.append(
                TransactionAttachment.from_api(
                    attachment,
                    transaction_id=transaction_id,
                    position=len(transaction.attachments),
                )
            )
            transaction.files_present = True
            await self._database.upsert(transaction)
        self.invalidate()

    async def delete_attachment(self, file_id: int) -> None:
        """Remove attachment metadata from its known cached owner."""
        await self._database.delete_transaction_attachment(file_id)
        self.invalidate()

    def invalidate(self) -> None:
        """Invalidate all operation-local transaction-derived reads."""
        self._memo.invalidate("transactions", "summary", "analytics")


class EphemeralTransactionAdapter:
    """Serve transactions live and retain no write projections."""

    def __init__(self, client: LunchMoneyApp, memo: OperationMemo) -> None:
        """Bind a non-retaining upstream client and operation memo."""
        self._client = client
        self._memo = memo

    async def list(self, query: TransactionQuery) -> builtins.list[TransactionObject]:
        """Consume every live transaction page for the complete query."""

        async def load() -> builtins.list[TransactionObject]:
            values = await self._client.refresh_transactions(
                cache=False, **query.model_dump(exclude_none=True)
            )
            return list(values.values())

        key = ("transactions:list", *sorted(query.model_dump(mode="json").items()))
        return await self._memo.get_or_create(key, load)

    async def get(
        self, transaction_id: int
    ) -> TransactionObject | ChildTransactionObject | None:
        """Return one live transaction graph, translating upstream not-found."""
        try:
            return await self._memo.get_or_create(
                ("transactions:detail", transaction_id),
                lambda: self._client.client.transactions.get_transaction_by_id(
                    id=transaction_id
                ),
            )
        except Exception as error:
            if getattr(error, "status", None) == 404:
                return None
            raise

    async def recent(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        limit: int,
    ) -> builtins.list[TransactionObject]:
        """Return the requested number of current recent transactions."""
        values = await self.list(
            TransactionQuery(
                start_date=start_date,
                end_date=end_date,
                include_pending=True,
                include_split_parents=False,
            )
        )
        return values[:limit]

    async def store_many(self, transactions: builtins.list[TransactionObject]) -> None:
        """Discard canonical write responses and invalidate operation reads."""
        del transactions
        self.invalidate()

    async def delete_many(self, transaction_ids: builtins.list[int]) -> None:
        """Retain no deletion projection and invalidate operation reads."""
        del transaction_ids
        self.invalidate()

    async def group_child_ids(self, transaction_id: int) -> builtins.list[int]:
        """Resolve group children from the upstream detail graph before mutation."""
        group = await self.get(transaction_id)
        if not isinstance(group, TransactionObject):
            return []
        return [item.id for item in group.children or []]

    async def replace_ungrouped(
        self, transaction_id: int, restored: builtins.list[TransactionObject]
    ) -> None:
        """Discard restored children and invalidate the operation graph."""
        del transaction_id, restored
        self.invalidate()

    async def replace_unsplit(
        self, transaction_id: int, restored: TransactionObject
    ) -> None:
        """Discard the restored parent and invalidate the operation graph."""
        del transaction_id, restored
        self.invalidate()

    async def store_attachment(
        self,
        transaction_id: int,
        attachment: TransactionAttachmentObject,
    ) -> None:
        """Discard attachment metadata and invalidate transaction reads."""
        del transaction_id, attachment
        self.invalidate()

    async def delete_attachment(self, file_id: int) -> None:
        """Retain no attachment deletion state and invalidate transaction reads."""
        del file_id
        self.invalidate()

    def invalidate(self) -> None:
        """Invalidate all operation-local transaction-derived reads."""
        self._memo.invalidate("transactions", "summary", "analytics")


__all__ = [
    "EphemeralTransactionAdapter",
    "StatefulTransactionAdapter",
    "TransactionAdapter",
]
