"""Persistence contract tests for relationship-aware async database helpers."""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta, timezone
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


def _mixed_child_transaction_record() -> Transaction:
    """Build a parent graph containing one split and one group child."""
    split_child = child_transaction_object(
        transaction_id=101,
        tag_ids=[22],
        files=None,
    )
    group_child = child_transaction_object(
        transaction_id=102,
        split_parent_id=None,
        group_parent_id=100,
        tag_ids=[22],
        files=None,
    )
    api_record = transaction_object(
        children=[split_child, group_child],
        is_group_parent=True,
        tag_ids=[21],
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


@pytest.mark.parametrize(
    "timestamp",
    [
        datetime(2026, 1, 2, 3, 4, 5),
        datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        datetime(
            2026,
            1,
            2,
            3,
            4,
            5,
            tzinfo=timezone(timedelta(hours=-7)),
        ),
    ],
    ids=["naive", "utc", "negative-offset"],
)
@pytest.mark.asyncio
async def test_persisted_scalar_and_category_timestamps_round_trip_exactly(
    database: LunchMoneyDatabase,
    timestamp: datetime,
) -> None:
    """Preserve exact API JSON timestamp shape across a SQLite reload."""
    api_plaid = plaid_account_object().model_copy(
        update={
            "balance_last_update": timestamp,
            "last_import": timestamp,
            "last_fetch": timestamp,
            "plaid_last_successful_update": timestamp,
        }
    )
    api_manual = manual_account_object().model_copy(
        update={
            "balance_as_of": timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )
    api_tag = tag_object().model_copy(
        update={
            "created_at": timestamp,
            "updated_at": timestamp,
            "archived_at": timestamp,
        }
    )
    api_child = child_category_object().model_copy(
        update={
            "created_at": timestamp,
            "updated_at": timestamp,
            "archived_at": timestamp,
        }
    )
    api_category = category_object(children=[api_child]).model_copy(
        update={
            "created_at": timestamp,
            "updated_at": timestamp,
            "archived_at": timestamp,
        }
    )
    api_records = [api_plaid, api_manual, api_tag, api_category]
    records = [
        PlaidAccount.from_api(api_plaid),
        ManualAccount.from_api(api_manual),
        Tag.from_api(api_tag),
        Category.from_api(api_category),
    ]

    stored = await database.upsert_many(records)

    assert [record.to_api().model_dump(mode="json") for record in stored] == [
        record.model_dump(mode="json") for record in api_records
    ]


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
async def test_upsert_many_orders_separate_category_parent_before_child(
    database: LunchMoneyDatabase,
) -> None:
    """Persist a child-first category batch while returning caller order."""
    api_child = child_category_object()
    parent = Category.from_api(category_object(children=None))
    child = Category.from_api(category_object(children=[api_child])).children[0]

    stored = await database.upsert_many([child, parent])

    assert [record.id for record in stored] == [child.id, parent.id]
    assert stored[0].to_api().id == api_child.id
    assert stored[0].parent is not None
    assert stored[0].parent.id == parent.id


@pytest.mark.asyncio
async def test_upsert_many_orders_separate_transaction_parent_before_child(
    database: LunchMoneyDatabase,
) -> None:
    """Persist a child-first transaction batch while returning caller order."""
    tags = [Tag.from_api(tag_object(21)), Tag.from_api(tag_object(22))]
    parent = Transaction.from_api(
        transaction_object(children=None),
        tags=tags,
    )
    api_child = child_transaction_object()
    child = Transaction.from_api(api_child, tags=tags)
    requested = [child, parent, *_dependency_records()]

    stored = await database.upsert_many(requested)

    assert [
        cast(
            User | PlaidAccount | ManualAccount | Category | Tag | Transaction, record
        ).id
        for record in stored
    ] == [101, 100, 1, 2, 3, 10, 21, 22]
    stored_child = stored[0]
    assert isinstance(stored_child, Transaction)
    assert stored_child.to_api().model_dump(mode="json") == api_child.model_dump(
        mode="json"
    )
    assert stored_child.split_parent is not None
    assert stored_child.split_parent.id == parent.id


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
async def test_transaction_child_upsert_removes_former_owned_graph(
    database: LunchMoneyDatabase,
) -> None:
    """Delete descendants when an existing parent transaction becomes a child."""
    await database.upsert_many(_dependency_records())
    tags = [Tag.from_api(tag_object(21)), Tag.from_api(tag_object(22))]
    former_child = child_transaction_object(
        transaction_id=101,
        tag_ids=[22],
        files=[transaction_attachment_object(attachment_id=601)],
    )
    await database.upsert(
        Transaction.from_api(
            transaction_object(children=[former_child]),
            tags=tags,
        )
    )
    await database.upsert(
        Transaction.from_api(
            transaction_object(transaction_id=200, children=None),
            tags=tags,
        )
    )

    moved = await database.upsert(
        Transaction.from_api(
            child_transaction_object(
                transaction_id=100,
                split_parent_id=200,
                tag_ids=[21],
                files=None,
            ),
            tags=tags,
        )
    )

    assert moved.split_parent_id == 200
    assert moved.split_children == []
    assert moved.group_children == []
    assert await database.get(Transaction, 101) is None
    async with database.session() as session:
        attachments = (
            await session.exec(
                select(TransactionAttachment).where(
                    TransactionAttachment.transaction_id == 101
                )
            )
        ).all()
    assert attachments == []


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
async def test_transaction_attachment_replacement_preserves_incoming_order(
    database: LunchMoneyDatabase,
) -> None:
    """Reload retained attachments in the replacement API list order."""
    await database.upsert_many(_dependency_records())
    await database.upsert(
        _transaction_record(
            attachment_ids=(501, 502),
            include_child=False,
        )
    )
    replacement = _transaction_record(
        attachment_ids=(502, 501),
        include_child=False,
    )

    updated = await database.upsert(replacement)
    reloaded = await database.get(Transaction, replacement.id)

    assert [attachment.api_id for attachment in updated.attachments] == [502, 501]
    assert reloaded is not None
    assert [attachment.api_id for attachment in reloaded.attachments] == [502, 501]
    converted = reloaded.to_api()
    assert [attachment.id for attachment in converted.files or []] == [502, 501]


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
async def test_get_detaches_transaction_category_and_child_parent_graphs(
    database: LunchMoneyDatabase,
) -> None:
    """Keep referenced category and nested parent access usable after get()."""
    transaction = _mixed_child_transaction_record()
    await database.upsert_many([*_dependency_records(), transaction])

    stored = await database.get(Transaction, transaction.id)

    assert stored is not None
    assert stored.category is not None
    assert stored.category.to_api().model_dump(mode="json") == (
        category_object(children=[child_category_object()]).model_dump(mode="json")
    )
    split_child = stored.split_children[0]
    group_child = stored.group_children[0]
    assert split_child.category is not None
    split_child.category.to_api()
    assert split_child.split_parent is stored
    assert split_child.group_parent is None
    assert group_child.category is not None
    group_child.category.to_api()
    assert group_child.group_parent is stored
    assert group_child.split_parent is None


@pytest.mark.asyncio
async def test_list_detaches_transaction_category_and_child_parent_graphs(
    database: LunchMoneyDatabase,
) -> None:
    """Keep referenced category and parent access usable after list()."""
    transaction = _mixed_child_transaction_record()
    await database.upsert_many([*_dependency_records(), transaction])

    listed = await database.list(Transaction)

    by_id = {record.id: record for record in listed}
    for record in listed:
        assert record.category is not None
        record.category.to_api()
    assert by_id[101].split_parent is by_id[100]
    assert by_id[101].group_parent is None
    assert by_id[102].group_parent is by_id[100]
    assert by_id[102].split_parent is None


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
