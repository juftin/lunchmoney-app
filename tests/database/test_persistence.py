"""Persistence contract tests for relationship-aware async database helpers."""

from collections.abc import Iterable
from typing import cast

import pytest
from lunchmoney.models import CategoryObject
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, select

from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import (
    Category,
    ManualAccount,
    PlaidAccount,
    Tag,
    Transaction,
    TransactionAttachment,
    TransactionTagLink,
    User,
)
from factories import (
    category_object,
    child_category_object,
    child_transaction_object,
    manual_account_object,
    plaid_account_object,
    tag_object,
    transaction_attachment_object,
    transaction_object,
    user_object,
)


class UnsupportedRecord(SQLModel):
    """Represent a valid SQLModel that the persistence API does not support."""

    id: int
    """Synthetic unsupported record identifier."""


def _assert_detached(record: SQLModel) -> None:
    """Assert that a persistence helper returned a session-independent record."""
    inspection = inspect(record)
    assert inspection is not None
    assert inspection.detached is True


def _dependency_records() -> list[SQLModel]:
    """Build all shared rows referenced by the synthetic transaction graph."""
    return [
        User.from_api(user_object()),
        PlaidAccount.from_api(plaid_account_object()),
        ManualAccount.from_api(manual_account_object()),
        Category.from_api(category_object(children=[child_category_object()])),
        Tag.from_api(tag_object(21)),
        Tag.from_api(tag_object(22)),
    ]


def _transaction_record(
    *,
    tag_ids: list[int] | None = None,
    attachment_ids: Iterable[int | None] = (501,),
    include_child: bool = True,
) -> Transaction:
    """Build a transaction graph whose foreign-key dependencies are available."""
    child = child_transaction_object(
        tag_ids=[22],
        files=[transaction_attachment_object(attachment_id=601)],
    )
    api_record = transaction_object(
        tag_ids=tag_ids if tag_ids is not None else [21],
        children=[child] if include_child else None,
        files=[
            transaction_attachment_object(attachment_id=attachment_id)
            for attachment_id in attachment_ids
        ],
    )
    tags = [Tag.from_api(tag_object(21)), Tag.from_api(tag_object(22))]
    return Transaction.from_api(api_record, tags=tags)


@pytest.mark.asyncio
async def test_scalar_upsert_inserts_and_updates(database: LunchMoneyDatabase) -> None:
    """Insert a scalar record and update that row without creating a duplicate."""
    inserted = await database.upsert(User.from_api(user_object()))
    changed = User.from_api(user_object())
    changed.name = "Updated Synthetic User"

    updated = await database.upsert(changed)
    stored = await database.list(User)

    assert inserted.id == changed.id
    assert updated.name == "Updated Synthetic User"
    assert [record.id for record in stored] == [changed.id]
    _assert_detached(updated)


@pytest.mark.asyncio
async def test_mixed_upsert_many_orders_dependencies_atomically(
    database: LunchMoneyDatabase,
) -> None:
    """Persist a reversed mixed batch while preserving the caller's result order."""
    records = [*_dependency_records(), _transaction_record()]
    reversed_records = list(reversed(records))

    stored = await database.upsert_many(iter(reversed_records))

    assert [type(record) for record in stored] == [
        type(record) for record in reversed_records
    ]
    transaction = stored[0]
    assert isinstance(transaction, Transaction)
    expected_transaction = cast(Transaction, reversed_records[0])
    assert transaction.to_api().model_dump(mode="json") == (
        expected_transaction.to_api().model_dump(mode="json")
    )
    _assert_detached(transaction)


@pytest.mark.asyncio
async def test_category_upsert_replaces_owned_children(
    database: LunchMoneyDatabase,
) -> None:
    """Update retained children and delete rows omitted from a category graph."""
    first_child = child_category_object()
    removed_child = first_child.model_copy(update={"id": 12, "name": "Removed"})
    await database.upsert(
        Category.from_api(category_object(children=[first_child, removed_child]))
    )
    retained_child = first_child.model_copy(update={"name": "Updated Child"})
    added_child = first_child.model_copy(
        update={"id": 13, "name": "Added Child", "order": 3}
    )

    updated = await database.upsert(
        Category.from_api(category_object(children=[retained_child, added_child]))
    )

    assert [(child.id, child.name) for child in updated.children] == [
        (11, "Updated Child"),
        (13, "Added Child"),
    ]
    assert await database.get(Category, 12) is None
    converted = updated.to_api()
    assert isinstance(converted, CategoryObject)
    assert [child.id for child in converted.children or []] == [11, 13]


@pytest.mark.asyncio
async def test_transaction_upsert_replaces_owned_children(
    database: LunchMoneyDatabase,
) -> None:
    """Update retained nested transactions and delete omitted child graphs."""
    await database.upsert_many(_dependency_records())
    first_child = child_transaction_object(
        transaction_id=101,
        tag_ids=[22],
        files=[transaction_attachment_object(attachment_id=601)],
    )
    removed_child = child_transaction_object(
        transaction_id=102,
        tag_ids=[22],
        files=[transaction_attachment_object(attachment_id=602)],
    )
    tags = [Tag.from_api(tag_object(21)), Tag.from_api(tag_object(22))]
    await database.upsert(
        Transaction.from_api(
            transaction_object(children=[first_child, removed_child]),
            tags=tags,
        )
    )
    retained_child = first_child.model_copy(update={"payee": "Updated Child Payee"})
    added_child = child_transaction_object(
        transaction_id=103,
        tag_ids=[22],
        files=[transaction_attachment_object(attachment_id=603)],
    )

    updated = await database.upsert(
        Transaction.from_api(
            transaction_object(children=[retained_child, added_child]),
            tags=tags,
        )
    )

    assert [(child.id, child.payee) for child in updated.split_children] == [
        (101, "Updated Child Payee"),
        (103, "Synthetic Child Payee"),
    ]
    assert await database.get(Transaction, 102) is None
    assert [link.tag_id for link in updated.split_children[0].tag_links] == [22]
    assert [
        attachment.api_id for attachment in updated.split_children[1].attachments
    ] == [603]


@pytest.mark.asyncio
async def test_transaction_upsert_replaces_attachments_and_tag_links(
    database: LunchMoneyDatabase,
) -> None:
    """Replace transaction-owned attachments and ordered tag associations."""
    await database.upsert_many(_dependency_records())
    await database.upsert(
        _transaction_record(
            tag_ids=[21, 22],
            attachment_ids=(501, None),
            include_child=False,
        )
    )
    replacement = _transaction_record(
        tag_ids=[22],
        attachment_ids=(502,),
        include_child=False,
    )

    updated = await database.upsert(replacement)

    assert [link.tag_id for link in updated.tag_links] == [22]
    assert [tag.id for tag in updated.tags] == [22]
    assert [attachment.api_id for attachment in updated.attachments] == [502]
    async with database.session() as session:
        links = (await session.exec(select(TransactionTagLink))).all()
        attachments = (await session.exec(select(TransactionAttachment))).all()
    assert [(link.transaction_id, link.tag_id) for link in links] == [(100, 22)]
    assert [attachment.api_id for attachment in attachments] == [502]


@pytest.mark.asyncio
async def test_get_and_list_return_detached_eager_graphs(
    database: LunchMoneyDatabase,
) -> None:
    """Keep every conversion relationship usable after helper sessions close."""
    transaction = _transaction_record()
    await database.upsert_many([*_dependency_records(), transaction])

    stored = await database.get(Transaction, transaction.id)
    listed = await database.list(Transaction)

    assert stored is not None
    _assert_detached(stored)
    assert stored.category is not None
    assert stored.plaid_account is not None
    assert [tag.id for tag in stored.tags] == [21]
    assert stored.split_children[0].manual_account is not None
    assert [tag.id for tag in stored.split_children[0].tags] == [22]
    assert stored.to_api().model_dump(mode="json") == transaction.to_api().model_dump(
        mode="json"
    )
    assert {record.id for record in listed} == {100, 101}
    for record in listed:
        _assert_detached(record)
        record.to_api()


@pytest.mark.asyncio
async def test_delete_returns_existence_and_cascades_owned_graphs(
    database: LunchMoneyDatabase,
) -> None:
    """Report deletion results and remove transaction and category dependents."""
    await database.upsert_many([*_dependency_records(), _transaction_record()])

    assert await database.delete(Transaction, 100) is True
    assert await database.delete(Transaction, 100) is False
    assert await database.get(Transaction, 101) is None
    async with database.session() as session:
        assert (await session.exec(select(TransactionTagLink))).all() == []
        assert (await session.exec(select(TransactionAttachment))).all() == []

    assert await database.delete(Category, 10) is True
    assert await database.get(Category, 11) is None


@pytest.mark.asyncio
async def test_delete_preserves_native_restrict_integrity_error(
    database: LunchMoneyDatabase,
) -> None:
    """Reject deletion of a shared record while a transaction references it."""
    await database.upsert_many([*_dependency_records(), _transaction_record()])

    with pytest.raises(IntegrityError):
        await database.delete(Tag, 21)

    assert await database.get(Tag, 21) is not None
    assert await database.get(Transaction, 100) is not None


@pytest.mark.asyncio
async def test_failed_batch_rolls_back_all_preceding_records(
    database: LunchMoneyDatabase,
) -> None:
    """Roll back valid earlier writes when a later dependency constraint fails."""
    invalid_transaction = Transaction.from_api(
        transaction_object(tag_ids=[999], children=None, files=None)
    )

    with pytest.raises(IntegrityError):
        await database.upsert_many([User.from_api(user_object()), invalid_transaction])

    assert await database.get(User, user_object().id) is None
    assert await database.get(Transaction, invalid_transaction.id) is None


@pytest.mark.asyncio
async def test_unsupported_models_raise_type_error_before_database_access(
    database: LunchMoneyDatabase,
) -> None:
    """Reject unsupported record values and classes through explicit dispatch."""
    unsupported = UnsupportedRecord(id=1)

    with pytest.raises(TypeError, match="Unsupported SQLModel record"):
        await database.upsert(unsupported)
    with pytest.raises(TypeError, match="Unsupported SQLModel record"):
        await database.upsert_many([User.from_api(user_object()), unsupported])
    with pytest.raises(TypeError, match="Unsupported SQLModel model"):
        await database.get(UnsupportedRecord, 1)
    with pytest.raises(TypeError, match="Unsupported SQLModel model"):
        await database.list(UnsupportedRecord)
    with pytest.raises(TypeError, match="Unsupported SQLModel model"):
        await database.delete(UnsupportedRecord, 1)
    assert await database.get(User, user_object().id) is None


@pytest.mark.asyncio
async def test_session_exposes_native_exec_and_explicit_commit(
    database: LunchMoneyDatabase,
) -> None:
    """Allow direct SQLModel queries while retaining caller-owned commit behavior."""
    async with database.session() as session:
        session.add(User.from_api(user_object()))
        await session.commit()
        records = (await session.exec(select(User))).all()
        connection = await session.connection()
        foreign_keys = (
            await connection.exec_driver_sql("PRAGMA foreign_keys")
        ).scalar_one()

    assert [record.id for record in records] == [user_object().id]
    assert foreign_keys == 1
