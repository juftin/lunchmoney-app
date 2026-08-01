"""Tests for normalized transaction graphs and related records."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import NoneType
from typing import get_args

import pytest
from lunchmoney.models import (
    ChildTransactionObject,
    TransactionAttachmentObject,
    TransactionObject,
)
from sqlalchemy import JSON, DateTime, Numeric, String, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from sqlalchemy.types import TypeDecorator
from sqlmodel import SQLModel, Session, create_engine, select

from lunchmoney_mcp.database.models import (
    Tag,
    Transaction,
    TransactionAttachment,
    TransactionKind,
    TransactionTagLink,
)
from factories import (
    child_transaction_object,
    tag_object,
    transaction_attachment_object,
    transaction_object,
)


UTC = timezone.utc
"""Canonical UTC timezone compatible with all supported Python versions."""


def test_transaction_graph_round_trip_is_exact() -> None:
    """Normalize every nested transaction value and reconstruct exact API JSON."""
    parent_tag = tag_object(tag_id=21)
    child_tag = tag_object(tag_id=22)
    child = child_transaction_object(
        files=[transaction_attachment_object(attachment_id=502)]
    )
    api_transaction = transaction_object(
        children=[child],
        files=[
            transaction_attachment_object(),
            transaction_attachment_object(attachment_id=None),
        ],
    )

    record = Transaction.from_api(
        api_transaction,
        tags=[Tag.from_api(parent_tag), Tag.from_api(child_tag)],
    )

    assert record.kind == TransactionKind.PARENT
    assert record.amount == Decimal(api_transaction.amount)
    assert record.to_base == Decimal(str(api_transaction.to_base))
    assert record.plaid_metadata_present is True
    assert record.custom_metadata_present is True
    assert [tag.id for tag in record.tags] == api_transaction.tag_ids
    assert [attachment.api_id for attachment in record.attachments] == [
        file.id for file in api_transaction.files or []
    ]
    assert [attachment.position for attachment in record.attachments] == [0, 1]
    assert [child.id for child in record.split_children] == [101]
    assert record.split_children[0].split_parent is record
    assert record.to_api().model_dump(mode="json") == api_transaction.model_dump(
        mode="json"
    )


def test_child_transaction_conversion_is_exact_and_deterministic() -> None:
    """Select the generated child schema using the persisted discriminator."""
    api_child = child_transaction_object(
        split_parent_id=None,
        tag_ids=[22],
        files=[transaction_attachment_object(attachment_id=None)],
    )
    record = Transaction.from_api(api_child, tags=[Tag.from_api(tag_object(22))])

    converted = record.to_api()

    assert record.kind == TransactionKind.CHILD
    assert isinstance(converted, ChildTransactionObject)
    assert isinstance(record.to_child_api(), ChildTransactionObject)
    assert converted.model_dump(mode="json") == api_child.model_dump(mode="json")


@pytest.mark.parametrize("children", [None, []])
@pytest.mark.parametrize("files", [None, []])
def test_parent_transaction_preserves_absent_and_empty_nested_states(
    children: list[ChildTransactionObject] | None,
    files: list[TransactionAttachmentObject] | None,
) -> None:
    """Preserve independent null and empty shapes for both parent nested fields."""
    api_transaction = transaction_object(
        children=children,
        files=files,
        is_split_parent=False,
    )

    converted = Transaction.from_api(api_transaction).to_api()

    assert isinstance(converted, TransactionObject)
    assert converted.model_dump(mode="json") == api_transaction.model_dump(mode="json")


@pytest.mark.parametrize("files", [None, []])
def test_child_transaction_preserves_absent_and_empty_files(
    files: list[TransactionAttachmentObject] | None,
) -> None:
    """Preserve the generated child's nullable attachment-list shape."""
    api_child = child_transaction_object(split_parent_id=None, tag_ids=[], files=files)

    converted = Transaction.from_api(api_child).to_api()

    assert isinstance(converted, ChildTransactionObject)
    assert converted.model_dump(mode="json") == api_child.model_dump(mode="json")


def test_transaction_from_api_marks_only_non_null_metadata_present() -> None:
    """Treat null API metadata as omitted while retaining native clear flags."""
    shallow_api = transaction_object(children=None, files=None).model_copy(
        update={"custom_metadata": None, "plaid_metadata": None}
    )

    record = Transaction.from_api(shallow_api)

    assert record.plaid_metadata_present is False
    assert record.custom_metadata_present is False


def test_split_and_group_relationships_are_independent() -> None:
    """Link nested rows to the correct self-parent using their API foreign key."""
    split_child = child_transaction_object(transaction_id=101, split_parent_id=100)
    split_parent = Transaction.from_api(
        transaction_object(children=[split_child], tag_ids=[])
    )
    group_child = child_transaction_object(
        transaction_id=201,
        split_parent_id=None,
        group_parent_id=200,
        tag_ids=[],
    )
    group_parent = Transaction.from_api(
        transaction_object(
            transaction_id=200,
            children=[group_child],
            tag_ids=[],
            is_split_parent=False,
            is_group_parent=True,
        )
    )

    assert split_parent.split_children[0].split_parent is split_parent
    assert split_parent.split_children[0].group_parent is None
    assert group_parent.group_children[0].group_parent is group_parent
    assert group_parent.group_children[0].split_parent is None
    assert split_parent.to_api().model_dump(mode="json") == transaction_object(
        children=[split_child], tag_ids=[]
    ).model_dump(mode="json")
    assert group_parent.to_api().model_dump(mode="json") == transaction_object(
        transaction_id=200,
        children=[group_child],
        tag_ids=[],
        is_split_parent=False,
        is_group_parent=True,
    ).model_dump(mode="json")


def test_persisted_split_children_retain_reverse_api_order() -> None:
    """Reload split children in their original global API order."""
    children = [
        child_transaction_object(
            transaction_id=transaction_id,
            tag_ids=[],
        ).model_copy(update={"category_id": None, "manual_account_id": None})
        for transaction_id in (102, 101)
    ]
    api_transaction = transaction_object(
        tag_ids=[],
        children=children,
        files=None,
    ).model_copy(update={"category_id": None, "plaid_account_id": None})
    record = Transaction.from_api(api_transaction)
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.expire_all()

        reloaded = session.get(Transaction, record.id)

        assert reloaded is not None
        assert [child.id for child in reloaded.split_children] == [102, 101]
        assert reloaded.to_api().model_dump(mode="json") == api_transaction.model_dump(
            mode="json"
        )


def test_mixed_children_retain_group_before_split_api_order() -> None:
    """Merge group and split relationships using their global API positions."""
    group_child = child_transaction_object(
        transaction_id=201,
        split_parent_id=None,
        group_parent_id=100,
        tag_ids=[],
    ).model_copy(update={"category_id": None, "manual_account_id": None})
    split_child = child_transaction_object(
        transaction_id=101,
        tag_ids=[],
    ).model_copy(update={"category_id": None, "manual_account_id": None})
    api_transaction = transaction_object(
        tag_ids=[],
        children=[group_child, split_child],
        files=None,
        is_group_parent=True,
    ).model_copy(update={"category_id": None, "plaid_account_id": None})
    record = Transaction.from_api(api_transaction)

    converted = record.to_api()

    assert isinstance(converted, TransactionObject)
    assert [child.id for child in converted.children or []] == [201, 101]

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.expire_all()

        reloaded = session.get(Transaction, record.id)

        assert reloaded is not None
        assert reloaded.to_api().model_dump(mode="json") == api_transaction.model_dump(
            mode="json"
        )


@pytest.mark.parametrize(
    ("split_parent_id", "group_parent_id"),
    [(None, None), (100, 100)],
    ids=["neither-parent-relation", "both-parent-relations"],
)
def test_parent_rejects_children_without_exactly_one_enclosing_relation(
    split_parent_id: int | None,
    group_parent_id: int | None,
) -> None:
    """Reject nested children whose ownership by the enclosing parent is unclear."""
    child = child_transaction_object(
        split_parent_id=split_parent_id,
        group_parent_id=group_parent_id,
        tag_ids=[],
    )
    api_transaction = transaction_object(children=[child], tag_ids=[])

    with pytest.raises(
        ValueError,
        match=(
            "Child transaction 101 must belong to exactly one split or group "
            "relationship on parent transaction 100"
        ),
    ):
        Transaction.from_api(api_transaction)


def test_transaction_table_covers_generated_scalar_union() -> None:
    """Map every parent/child scalar field plus conversion-state columns."""
    api_fields = set(TransactionObject.model_fields) | set(
        ChildTransactionObject.model_fields
    )
    table = SQLModel.metadata.tables["transactions"]

    assert set(table.c.keys()) == api_fields - {
        "tag_ids",
        "children",
        "files",
    } | {
        "child_position",
        "children_present",
        "created_at_offset_minutes",
        "files_present",
        "kind",
        "plaid_metadata_present",
        "custom_metadata_present",
        "updated_at_offset_minutes",
    }
    assert table.c.child_position.nullable is True
    assert isinstance(table.c.kind.type, String)
    assert table.c.children_present.nullable is False
    assert table.c.files_present.nullable is False
    assert table.c.plaid_metadata_present.nullable is False
    assert table.c.custom_metadata_present.nullable is False
    assert table.c.created_at_offset_minutes.nullable is True
    assert table.c.updated_at_offset_minutes.nullable is True


def test_transaction_scalar_columns_match_generated_requirements() -> None:
    """Mirror generated scalar requiredness, defaults, and database nullability."""
    api_fields = {
        field_name: field
        for api_type in (TransactionObject, ChildTransactionObject)
        for field_name, field in api_type.model_fields.items()
        if field_name not in {"tag_ids", "children", "files"}
    }
    table = SQLModel.metadata.tables["transactions"]

    for field_name, api_field in api_fields.items():
        record_field = Transaction.model_fields[field_name]

        assert record_field.is_required() is api_field.is_required()
        assert record_field.default == api_field.default
        assert table.c[field_name].nullable is (
            NoneType in get_args(api_field.annotation)
        )
    for field_name in ("created_at", "updated_at"):
        column_type = table.c[field_name].type
        assert isinstance(column_type, TypeDecorator)
        assert isinstance(column_type.impl, DateTime)
        assert column_type.impl.timezone is True


def test_nullable_transaction_and_attachment_fields_round_trip() -> None:
    """Preserve null across every generated field that permits it."""
    values = transaction_object(tag_ids=[], children=None, files=None).model_dump()
    for field_name, field in TransactionObject.model_fields.items():
        if NoneType in get_args(field.annotation):
            values[field_name] = None
    api_transaction = TransactionObject.model_validate(values)
    api_attachment = TransactionAttachmentObject()

    transaction_converted = Transaction.from_api(api_transaction).to_api()
    attachment_converted = TransactionAttachment.from_api(
        api_attachment,
        transaction_id=api_transaction.id,
        position=0,
    ).to_api()

    assert transaction_converted.model_dump(mode="json") == api_transaction.model_dump(
        mode="json"
    )
    assert attachment_converted.model_dump(mode="json") == api_attachment.model_dump(
        mode="json"
    )


def test_transaction_columns_use_portable_precise_and_json_types() -> None:
    """Store money precisely and arbitrary metadata in portable JSON columns."""
    record = Transaction.from_api(transaction_object(tag_ids=[]))
    table = SQLModel.metadata.tables["transactions"]

    assert isinstance(record.amount, Decimal)
    assert isinstance(record.to_base, Decimal)
    for column_name in ("amount", "to_base"):
        column_type = table.c[column_name].type
        assert isinstance(column_type, Numeric)
        assert column_type.precision == 20
        assert column_type.scale == 10
    for column_name in ("plaid_metadata", "custom_metadata"):
        assert isinstance(table.c[column_name].type, JSON)
        assert getattr(record, column_name) == getattr(
            transaction_object(tag_ids=[]), column_name
        )


def test_transaction_foreign_keys_reference_normalized_tables() -> None:
    """Use native foreign keys for accounts, categories, and both parent roles."""
    table = SQLModel.metadata.tables["transactions"]

    expected_targets = {
        "category_id": "categories.id",
        "plaid_account_id": "plaid_accounts.id",
        "manual_account_id": "manual_accounts.id",
        "split_parent_id": "transactions.id",
        "group_parent_id": "transactions.id",
    }
    for column_name, target in expected_targets.items():
        assert {
            foreign_key.target_fullname
            for foreign_key in table.c[column_name].foreign_keys
        } == {target}


def test_transaction_tag_link_uses_composite_primary_key() -> None:
    """Represent transaction tag IDs with a normalized composite-key link table."""
    table = SQLModel.metadata.tables["transaction_tag_links"]

    assert set(table.c.keys()) == {"transaction_id", "tag_id", "position"}
    assert {column.name for column in table.primary_key.columns} == {
        "transaction_id",
        "tag_id",
    }
    assert {
        foreign_key.target_fullname
        for foreign_key in table.c.transaction_id.foreign_keys
    } == {"transactions.id"}
    assert {
        foreign_key.target_fullname for foreign_key in table.c.tag_id.foreign_keys
    } == {"tags.id"}


def test_transaction_attachment_maps_api_id_to_nullable_indexed_column() -> None:
    """Separate generated storage identity from the optional Lunch Money ID."""
    api_fields = set(TransactionAttachmentObject.model_fields)
    table = SQLModel.metadata.tables["transaction_attachments"]

    assert set(table.c.keys()) == api_fields - {"id"} | {
        "id",
        "api_id",
        "created_at_offset_minutes",
        "position",
        "transaction_id",
    }
    assert table.c.id.primary_key is True
    assert table.c.id.autoincrement in {True, "auto"}
    assert table.c.api_id.nullable is True
    assert table.c.api_id.index is True
    assert table.c.position.nullable is False
    assert {
        foreign_key.target_fullname
        for foreign_key in table.c.transaction_id.foreign_keys
    } == {"transactions.id"}


def test_transaction_relationships_own_nested_records() -> None:
    """Configure native associations and orphan deletion for graph-owned rows."""
    mapper = inspect(Transaction)
    table = SQLModel.metadata.tables["transactions"]

    assert (
        mapper.relationships["tags"].secondary
        is SQLModel.metadata.tables["transaction_tag_links"]
    )
    for relationship_name in ("tag_links", "attachments"):
        relationship = mapper.relationships[relationship_name]
        assert relationship.cascade.delete is True
        assert relationship.cascade.delete_orphan is True
        assert relationship.single_parent is True
    attachment_table = SQLModel.metadata.tables["transaction_attachments"]
    assert tuple(mapper.relationships["attachments"].order_by) == (
        attachment_table.c.position,
    )
    for parent_name, children_name, foreign_key_name in (
        ("split_parent", "split_children", "split_parent_id"),
        ("group_parent", "group_children", "group_parent_id"),
    ):
        parent_relationship = mapper.relationships[parent_name]
        children_relationship = mapper.relationships[children_name]
        assert parent_relationship.back_populates == children_name
        assert parent_relationship.remote_side == {table.c.id}
        assert children_relationship.back_populates == parent_name
        assert children_relationship.single_parent is True
        assert children_relationship.cascade.delete is True
        assert children_relationship.cascade.delete_orphan is True
        assert children_relationship._calculated_foreign_keys == {
            table.c[foreign_key_name]
        }
        assert tuple(children_relationship.order_by) == (table.c.child_position,)


def test_owned_and_referenced_foreign_keys_declare_delete_actions() -> None:
    """Cascade owned rows while restricting deletion of shared references."""
    transaction_table = SQLModel.metadata.tables["transactions"]
    link_table = SQLModel.metadata.tables["transaction_tag_links"]
    attachment_table = SQLModel.metadata.tables["transaction_attachments"]

    for column_name in ("split_parent_id", "group_parent_id"):
        foreign_key = next(iter(transaction_table.c[column_name].foreign_keys))
        assert foreign_key.ondelete == "CASCADE"
    for column_name in ("category_id", "plaid_account_id", "manual_account_id"):
        foreign_key = next(iter(transaction_table.c[column_name].foreign_keys))
        assert foreign_key.ondelete == "RESTRICT"
    assert next(iter(link_table.c.transaction_id.foreign_keys)).ondelete == "CASCADE"
    assert next(iter(link_table.c.tag_id.foreign_keys)).ondelete == "RESTRICT"
    assert (
        next(iter(attachment_table.c.transaction_id.foreign_keys)).ondelete == "CASCADE"
    )


def test_persisted_tag_ids_retain_api_order() -> None:
    """Reload tag links in their original API list order."""
    tags = [Tag.from_api(tag_object(tag_id=tag_id)) for tag_id in (22, 21)]
    api_transaction = transaction_object(
        tag_ids=[22, 21],
        children=None,
        files=None,
        is_split_parent=False,
    ).model_copy(update={"category_id": None, "plaid_account_id": None})
    record = Transaction.from_api(api_transaction, tags=tags)
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.expire_all()

        reloaded = session.get(Transaction, record.id)

        assert reloaded is not None
        assert [tag.id for tag in reloaded.tags] == api_transaction.tag_ids
        assert reloaded.to_api().tag_ids == api_transaction.tag_ids


@pytest.mark.parametrize(
    ("timestamp", "expected_json"),
    [
        (datetime(2026, 1, 2, 3, 4, 5), "2026-01-02T03:04:05"),
        (datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC), "2026-01-02T03:04:05Z"),
        (
            datetime(
                2026,
                1,
                2,
                3,
                4,
                5,
                tzinfo=timezone(timedelta(hours=5, minutes=30)),
            ),
            "2026-01-02T03:04:05+05:30",
        ),
    ],
    ids=["naive", "utc", "positive-offset"],
)
def test_persisted_timestamps_round_trip_exact_source_shape(
    timestamp: datetime,
    expected_json: str,
) -> None:
    """Retain naive and aware source representations after a SQLite reload."""
    api_attachment = transaction_attachment_object().model_copy(
        update={"created_at": timestamp}
    )
    api_transaction = transaction_object(
        tag_ids=[],
        children=None,
        files=[api_attachment],
        is_split_parent=False,
    ).model_copy(
        update={
            "category_id": None,
            "created_at": timestamp,
            "plaid_account_id": None,
            "updated_at": timestamp,
        }
    )
    record = Transaction.from_api(api_transaction)
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.expire_all()

        reloaded = session.get(Transaction, record.id)

        assert reloaded is not None
        converted_json = reloaded.to_api().model_dump(mode="json")
        assert converted_json["created_at"] == expected_json
        assert converted_json["updated_at"] == expected_json
        assert converted_json["files"][0]["created_at"] == expected_json
        assert reloaded.to_api().model_dump(mode="json") == api_transaction.model_dump(
            mode="json"
        )


def test_transaction_tables_compile_for_postgresql() -> None:
    """Keep native timezone-aware datetime columns portable to PostgreSQL."""
    for table_name in (
        "transactions",
        "transaction_tag_links",
        "transaction_attachments",
    ):
        table = SQLModel.metadata.tables[table_name]

        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))

        assert f"CREATE TABLE {table_name}" in ddl
        if table_name != "transaction_tag_links":
            assert "TIMESTAMP WITH TIME ZONE" in ddl


def test_persisted_transaction_graph_round_trips_and_cascades() -> None:
    """Generate internal attachment keys and delete all owned graph rows."""
    tag = Tag.from_api(tag_object(tag_id=21))
    child = child_transaction_object(
        tag_ids=[],
        files=[transaction_attachment_object(attachment_id=None)],
    ).model_copy(update={"category_id": None, "manual_account_id": None})
    api_transaction = transaction_object(
        tag_ids=[21],
        children=[child],
        files=[
            transaction_attachment_object(attachment_id=None),
            transaction_attachment_object(attachment_id=None).model_copy(
                update={"name": "second-unidentified-attachment.pdf"}
            ),
        ],
    ).model_copy(update={"category_id": None, "plaid_account_id": None})
    record = Transaction.from_api(api_transaction, tags=[tag])
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.expire_all()

        reloaded = session.get(Transaction, record.id)

        assert reloaded is not None
        assert len(reloaded.attachments) == 2
        assert all(attachment.id is not None for attachment in reloaded.attachments)
        assert len({attachment.id for attachment in reloaded.attachments}) == 2
        assert [tag.id for tag in reloaded.tags] == api_transaction.tag_ids
        assert [nested.id for nested in reloaded.split_children] == [child.id]

        session.delete(reloaded)
        session.commit()

        assert session.exec(select(TransactionAttachment)).all() == []
        assert session.exec(select(TransactionTagLink)).all() == []
        assert session.get(Transaction, child.id) is None
        assert session.get(Tag, tag.id) is not None
