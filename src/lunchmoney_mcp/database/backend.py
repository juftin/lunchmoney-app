"""Async SQLModel database configuration and lifecycle helpers."""

import os
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Any, Self, cast

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import QueryableAttribute, selectinload
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from lunchmoney_mcp.database.models import (
    Category,
    ManualAccount,
    PlaidAccount,
    Tag,
    Transaction,
    TransactionAttachment,
    TransactionKind,
    TransactionTagLink,
    User,
)

DEFAULT_DATABASE_URL: str = "sqlite+aiosqlite:///lunchmoney.db"
"""Persistent SQLite database URL used when no URL is configured."""

_SUPPORTED_MODELS: frozenset[type[SQLModel]] = frozenset(
    {User, PlaidAccount, ManualAccount, Category, Tag, Transaction}
)
"""Explicit record classes accepted by the convenience persistence API."""


def resolve_database_url(database_url: str | None = None) -> str:
    """Resolve an explicit, environment-provided, or default database URL."""
    if database_url is not None:
        return database_url
    return os.getenv("LUNCHMONEY_DATABASE_URL", DEFAULT_DATABASE_URL)


def _enable_sqlite_foreign_keys(
    dbapi_connection: Any,
    connection_record: Any,
) -> None:
    """Enable SQLite foreign-key enforcement on one newly opened connection."""
    del connection_record
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def _ensure_supported_model(model: type[SQLModel]) -> None:
    """Reject model classes outside the explicitly supported public records."""
    if model not in _SUPPORTED_MODELS:
        msg = f"Unsupported SQLModel model: {model.__name__}"
        raise TypeError(msg)


def _ensure_supported_record(record: SQLModel) -> None:
    """Reject record instances outside the explicitly supported public records."""
    if type(record) not in _SUPPORTED_MODELS:
        msg = f"Unsupported SQLModel record: {type(record).__name__}"
        raise TypeError(msg)


def _dependency_order(record: SQLModel) -> int:
    """Return the foreign-key-safe persistence order for a supported record."""
    record_type = type(record)
    if record_type is User:
        return 0
    if record_type in {PlaidAccount, ManualAccount}:
        return 1
    if record_type is Category:
        return 2
    if record_type is Tag:
        return 3
    if record_type is Transaction:
        return 4
    msg = f"Unsupported SQLModel record: {record_type.__name__}"
    raise TypeError(msg)


def _record_primary_key(record: SQLModel) -> int:
    """Return the integer primary key of an explicitly supported record."""
    record_type = type(record)
    if record_type is User:
        return cast(User, record).id
    if record_type is PlaidAccount:
        return cast(PlaidAccount, record).id
    if record_type is ManualAccount:
        return cast(ManualAccount, record).id
    if record_type is Category:
        return cast(Category, record).id
    if record_type is Tag:
        return cast(Tag, record).id
    if record_type is Transaction:
        return cast(Transaction, record).id
    msg = f"Unsupported SQLModel record: {record_type.__name__}"
    raise TypeError(msg)


def _primary_key_attribute(model: type[SQLModel]) -> Any:
    """Return the mapped identifier attribute for a supported model class."""
    if model is User:
        return User.id
    if model is PlaidAccount:
        return PlaidAccount.id
    if model is ManualAccount:
        return ManualAccount.id
    if model is Category:
        return Category.id
    if model is Tag:
        return Tag.id
    if model is Transaction:
        return Transaction.id
    msg = f"Unsupported SQLModel model: {model.__name__}"
    raise TypeError(msg)


def _loader_attribute(value: Any) -> QueryableAttribute[Any]:
    """Narrow a SQLModel relationship annotation to its mapped class attribute."""
    return cast(QueryableAttribute[Any], value)


def _eager_options(model: type[SQLModel]) -> tuple[Any, ...]:
    """Return explicit eager-loading rules for one supported record class."""
    if model is Category:
        parent = _loader_attribute(Category.parent)
        children = _loader_attribute(Category.children)
        return (
            selectinload(parent),
            selectinload(children),
            selectinload(parent).selectinload(children),
            selectinload(children).selectinload(parent),
        )
    if model is Transaction:
        category = _loader_attribute(Transaction.category)
        plaid_account = _loader_attribute(Transaction.plaid_account)
        manual_account = _loader_attribute(Transaction.manual_account)
        split_parent = _loader_attribute(Transaction.split_parent)
        group_parent = _loader_attribute(Transaction.group_parent)
        tag_links = _loader_attribute(Transaction.tag_links)
        link_tag = _loader_attribute(TransactionTagLink.tag)
        tags = _loader_attribute(Transaction.tags)
        attachments = _loader_attribute(Transaction.attachments)
        split_children = _loader_attribute(Transaction.split_children)
        group_children = _loader_attribute(Transaction.group_children)
        return (
            selectinload(category),
            selectinload(plaid_account),
            selectinload(manual_account),
            selectinload(split_parent),
            selectinload(group_parent),
            selectinload(tag_links).selectinload(link_tag),
            selectinload(tags),
            selectinload(attachments),
            selectinload(split_children).selectinload(category),
            selectinload(split_children).selectinload(plaid_account),
            selectinload(split_children).selectinload(manual_account),
            selectinload(split_children).selectinload(tag_links).selectinload(link_tag),
            selectinload(split_children).selectinload(tags),
            selectinload(split_children).selectinload(attachments),
            selectinload(group_children).selectinload(category),
            selectinload(group_children).selectinload(plaid_account),
            selectinload(group_children).selectinload(manual_account),
            selectinload(group_children).selectinload(tag_links).selectinload(link_tag),
            selectinload(group_children).selectinload(tags),
            selectinload(group_children).selectinload(attachments),
        )
    return ()


def _clone_category_graph(record: Category) -> Category:
    """Copy a transient category graph without carrying ORM session state."""
    clone = Category.model_validate(record.model_dump())
    clone.children = [
        Category.model_validate(child.model_dump()) for child in record.children
    ]
    return clone


def _clone_transaction_graph(record: Transaction) -> Transaction:
    """Copy a transaction graph without shared records or ORM session state."""
    clone = Transaction.model_validate(record.model_dump())
    clone.tag_links = [
        TransactionTagLink.model_validate(link.model_dump())
        for link in record.tag_links
    ]
    clone.attachments = [
        TransactionAttachment.model_validate(attachment.model_dump())
        for attachment in record.attachments
    ]
    clone.split_children = [
        _clone_transaction_graph(child) for child in record.split_children
    ]
    clone.group_children = [
        _clone_transaction_graph(child) for child in record.group_children
    ]
    return clone


def _replacement_attachments(
    existing: Transaction,
    incoming: Transaction,
) -> list[TransactionAttachment]:
    """Reconcile attachment identity while replacing an owned collection."""
    by_id = {
        attachment.id: attachment
        for attachment in existing.attachments
        if attachment.id is not None
    }
    by_api_id = {
        attachment.api_id: attachment
        for attachment in existing.attachments
        if attachment.api_id is not None
    }
    used: set[int] = set()
    replacement: list[TransactionAttachment] = []
    for attachment in incoming.attachments:
        managed = by_id.get(attachment.id) if attachment.id is not None else None
        if managed is None and attachment.api_id is not None:
            managed = by_api_id.get(attachment.api_id)
        if managed is not None and id(managed) not in used:
            managed.sqlmodel_update(attachment.model_dump(exclude={"id"}))
            managed.transaction_id = existing.id
            used.add(id(managed))
            replacement.append(managed)
            continue
        clone = TransactionAttachment.model_validate(attachment.model_dump())
        clone.transaction_id = existing.id
        replacement.append(clone)
    return replacement


def _replacement_tag_links(
    existing: Transaction,
    incoming: Transaction,
) -> list[TransactionTagLink]:
    """Reconcile composite link identity while replacing tag associations."""
    by_tag_id = {link.tag_id: link for link in existing.tag_links}
    replacement: list[TransactionTagLink] = []
    for link in incoming.tag_links:
        managed = by_tag_id.get(link.tag_id)
        if managed is not None:
            managed.position = link.position
            replacement.append(managed)
            continue
        replacement.append(
            TransactionTagLink(
                transaction_id=existing.id,
                tag_id=link.tag_id,
                position=link.position,
            )
        )
    return replacement


def _update_category_graph(existing: Category, incoming: Category) -> None:
    """Update category scalars and atomically replace its owned children."""
    existing.sqlmodel_update(incoming)
    by_id = {child.id: child for child in existing.children}
    replacement: list[Category] = []
    for child in incoming.children:
        managed = by_id.get(child.id)
        if managed is not None:
            managed.sqlmodel_update(child)
            managed.group_id = existing.id
            replacement.append(managed)
            continue
        clone = Category.model_validate(child.model_dump())
        clone.group_id = existing.id
        replacement.append(clone)
    existing.children = replacement


def _update_transaction_graph(existing: Transaction, incoming: Transaction) -> None:
    """Update transaction scalars and atomically replace every owned collection."""
    existing.sqlmodel_update(incoming)
    existing.attachments = _replacement_attachments(existing, incoming)
    existing.tag_links = _replacement_tag_links(existing, incoming)

    if TransactionKind(incoming.kind) is TransactionKind.CHILD:
        return

    managed_children = {
        child.id: child
        for child in [*existing.split_children, *existing.group_children]
    }

    split_replacement: list[Transaction] = []
    for child in incoming.split_children:
        managed = managed_children.get(child.id)
        if managed is None:
            managed = _clone_transaction_graph(child)
        else:
            _update_transaction_graph(managed, child)
        managed.split_parent_id = existing.id
        managed.group_parent_id = None
        split_replacement.append(managed)

    group_replacement: list[Transaction] = []
    for child in incoming.group_children:
        managed = managed_children.get(child.id)
        if managed is None:
            managed = _clone_transaction_graph(child)
        else:
            _update_transaction_graph(managed, child)
        managed.split_parent_id = None
        managed.group_parent_id = existing.id
        group_replacement.append(managed)

    existing.split_children = split_replacement
    existing.group_children = group_replacement


async def _load_record[RecordT: SQLModel](
    session: AsyncSession,
    model: type[RecordT],
    primary_key: int,
) -> RecordT | None:
    """Load one supported record with its explicit detached-record graph."""
    supported_model = cast(type[SQLModel], model)
    statement = (
        select(model)
        .where(_primary_key_attribute(supported_model) == primary_key)
        .options(*_eager_options(supported_model))
    )
    result = await session.exec(statement)
    return result.one_or_none()


async def _upsert_record(session: AsyncSession, record: SQLModel) -> None:
    """Insert or update one supported record without committing its session."""
    record_type = type(record)
    primary_key = _record_primary_key(record)
    if record_type is Category:
        category = cast(Category, record)
        existing_category = await _load_record(session, Category, primary_key)
        if existing_category is None:
            session.add(_clone_category_graph(category))
        else:
            _update_category_graph(existing_category, category)
        return
    if record_type is Transaction:
        transaction = cast(Transaction, record)
        existing_transaction = await _load_record(session, Transaction, primary_key)
        if existing_transaction is None:
            session.add(_clone_transaction_graph(transaction))
        else:
            _update_transaction_graph(existing_transaction, transaction)
        return

    existing = await session.get(record_type, primary_key)
    if existing is None:
        session.add(record)
    else:
        existing.sqlmodel_update(record)


class LunchMoneyDatabase:
    """Own the application's async database engine and session factory."""

    engine: AsyncEngine
    """Engine used for all database connections."""
    session_factory: async_sessionmaker[AsyncSession]
    """Factory that creates native SQLModel asynchronous sessions."""

    def __init__(self, database_url: str | None = None) -> None:
        """Create database resources for the resolved connection URL."""
        self.engine = create_async_engine(resolve_database_url(database_url))
        if self.engine.dialect.name == "sqlite":
            event.listen(
                self.engine.sync_engine,
                "connect",
                _enable_sqlite_foreign_keys,
            )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session and close it without committing caller operations."""
        async with self.session_factory() as session:
            yield session

    async def upsert[RecordT: SQLModel](self, record: RecordT) -> RecordT:
        """Atomically insert or update one supported record and its owned graph."""
        return (await self.upsert_many((record,)))[0]

    async def upsert_many[RecordT: SQLModel](
        self,
        records: Iterable[RecordT],
    ) -> list[RecordT]:
        """Atomically persist records in foreign-key-safe dependency order."""
        requested = list(records)
        for record in requested:
            _ensure_supported_record(record)
        ordered = sorted(
            enumerate(requested),
            key=lambda item: (_dependency_order(item[1]), item[0]),
        )

        if not requested:
            return []

        stored_by_index: dict[int, RecordT] = {}
        async with self.session_factory() as session:
            async with session.begin():
                for _, record in ordered:
                    await _upsert_record(session, record)
                await session.flush()
                session.expunge_all()
                for index, record in enumerate(requested):
                    stored = await _load_record(
                        session,
                        type(record),
                        _record_primary_key(record),
                    )
                    if stored is None:
                        msg = (
                            f"Persisted {type(record).__name__} "
                            f"{_record_primary_key(record)} could not be reloaded"
                        )
                        raise RuntimeError(msg)
                    stored_by_index[index] = stored
        return [stored_by_index[index] for index in range(len(requested))]

    async def get[RecordT: SQLModel](
        self,
        model: type[RecordT],
        primary_key: int,
    ) -> RecordT | None:
        """Return one detached supported record with required relationships loaded."""
        _ensure_supported_model(cast(type[SQLModel], model))
        async with self.session_factory() as session:
            return await _load_record(session, model, primary_key)

    async def list[RecordT: SQLModel](
        self,
        model: type[RecordT],
    ) -> list[RecordT]:
        """Return all detached records with type-specific relationships loaded."""
        supported_model = cast(type[SQLModel], model)
        _ensure_supported_model(supported_model)
        statement = (
            select(model)
            .options(*_eager_options(supported_model))
            .order_by(_primary_key_attribute(supported_model))
        )
        async with self.session_factory() as session:
            result = await session.exec(statement)
            return list(result.all())

    async def delete[RecordT: SQLModel](
        self,
        model: type[RecordT],
        primary_key: int,
    ) -> bool:
        """Atomically delete one supported row and report whether it existed."""
        _ensure_supported_model(cast(type[SQLModel], model))
        async with self.session_factory() as session:
            async with session.begin():
                record = await _load_record(session, model, primary_key)
                if record is None:
                    return False
                await session.delete(record)
            return True

    async def __aenter__(self) -> Self:
        """Return this database instance for async context manager use."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Dispose engine resources when leaving an async context manager."""
        await self.dispose()

    async def dispose(self) -> None:
        """Release all connections held by the underlying async engine."""
        await self.engine.dispose()
