"""Tests for scalar SQLModel records and generated API conversions."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any, Protocol

import pytest
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, Numeric, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from sqlalchemy.types import TypeDecorator
from sqlmodel import SQLModel

from lunchmoney_mcp.database.models import ManualAccount, PlaidAccount, Tag, User
from factories import (
    manual_account_object,
    plaid_account_object,
    tag_object,
    user_object,
)


class _RoundTripRecord(Protocol):
    """Describe the scalar-record API conversion used by parametrized tests."""

    def to_api(self) -> BaseModel:
        """Convert this record back to its generated API model."""
        ...


ROUND_TRIP_CASES: list[
    tuple[Callable[[], BaseModel], Callable[[Any], _RoundTripRecord]]
] = [
    (user_object, User.from_api),
    (plaid_account_object, PlaidAccount.from_api),
    (manual_account_object, ManualAccount.from_api),
    (tag_object, Tag.from_api),
]
"""Generated factories paired with their SQLModel conversion methods."""

ACCOUNT_BALANCE_ROUND_TRIP_CASES: list[
    tuple[Callable[[], BaseModel], Callable[[Any], _RoundTripRecord], str]
] = [
    (plaid_account_object, PlaidAccount.from_api, "1250.5000"),
    (manual_account_object, ManualAccount.from_api, "750.2500"),
]
"""Four-decimal balance fixtures paired with their SQLModel conversion methods."""

TIMESTAMP_FIELDS_BY_RECORD: dict[type[SQLModel], tuple[str, ...]] = {
    PlaidAccount: (
        "balance_last_update",
        "last_import",
        "last_fetch",
        "plaid_last_successful_update",
    ),
    ManualAccount: ("balance_as_of", "created_at", "updated_at"),
    Tag: ("updated_at", "created_at", "archived_at"),
}
"""Timestamp fields whose source offsets require persisted conversion state."""

TABLE_NAME_BY_RECORD: dict[type[SQLModel], str] = {
    PlaidAccount: "plaid_accounts",
    ManualAccount: "manual_accounts",
    Tag: "tags",
}
"""Explicit table names for scalar records with timestamp state."""


@pytest.mark.parametrize(("api_factory", "record_factory"), ROUND_TRIP_CASES)
def test_scalar_record_round_trip_is_exact(
    api_factory: Callable[[], BaseModel],
    record_factory: Callable[[Any], _RoundTripRecord],
) -> None:
    """Preserve every generated value through an API-record-API round trip."""
    api_model = api_factory()

    round_tripped = record_factory(api_model).to_api()

    assert round_tripped.model_dump(mode="json") == api_model.model_dump(mode="json")


@pytest.mark.parametrize(
    ("api_factory", "record_factory", "expected_balance"),
    ACCOUNT_BALANCE_ROUND_TRIP_CASES,
)
def test_account_balance_round_trip_preserves_four_decimal_api_strings(
    api_factory: Callable[[], BaseModel],
    record_factory: Callable[[Any], _RoundTripRecord],
    expected_balance: str,
) -> None:
    """Preserve Lunch Money's canonical four-decimal account balances exactly."""
    api_model = api_factory()

    round_tripped = record_factory(api_model).to_api()

    assert api_model.model_dump(mode="json")["balance"] == expected_balance
    assert round_tripped.model_dump(mode="json") == api_model.model_dump(mode="json")


@pytest.mark.parametrize(
    ("record_type", "api_type"),
    [
        (User, type(user_object())),
        (PlaidAccount, type(plaid_account_object())),
        (ManualAccount, type(manual_account_object())),
        (Tag, type(tag_object())),
    ],
)
def test_scalar_records_cover_every_generated_field(
    record_type: type[SQLModel], api_type: type[BaseModel]
) -> None:
    """Declare every API field plus explicit timestamp source-shape state."""
    expected_fields = set(api_type.model_fields) | {
        f"{field_name}_offset_minutes"
        for field_name in TIMESTAMP_FIELDS_BY_RECORD.get(record_type, ())
    }

    assert set(record_type.model_fields) == expected_fields


@pytest.mark.parametrize(
    ("record_type", "api_type"),
    [
        (User, type(user_object())),
        (PlaidAccount, type(plaid_account_object())),
        (ManualAccount, type(manual_account_object())),
        (Tag, type(tag_object())),
    ],
)
def test_scalar_records_match_generated_field_requirements_and_defaults(
    record_type: type[SQLModel], api_type: type[BaseModel]
) -> None:
    """Mirror generated requiredness and defaults for every scalar field."""
    for field_name, api_field in api_type.model_fields.items():
        record_field = record_type.model_fields[field_name]

        assert record_field.is_required() is api_field.is_required()
        assert record_field.default == api_field.default


def test_monetary_fields_are_decimal_numeric_columns() -> None:
    """Represent account monetary values with precise decimal numeric columns."""
    plaid_account = PlaidAccount.from_api(plaid_account_object())
    manual_account = ManualAccount.from_api(manual_account_object())

    assert isinstance(plaid_account.limit, Decimal)
    assert isinstance(plaid_account.balance, Decimal)
    assert isinstance(plaid_account.to_base, Decimal)
    assert isinstance(manual_account.balance, Decimal)
    assert isinstance(manual_account.to_base, Decimal)

    for table_name, column_names in {
        "plaid_accounts": ("limit", "balance", "to_base"),
        "manual_accounts": ("balance", "to_base"),
    }.items():
        table = SQLModel.metadata.tables[table_name]
        for column_name in column_names:
            column_type = table.c[column_name].type
            assert isinstance(column_type, Numeric)
            assert column_type.precision == 20
            assert column_type.scale == 10

    assert SQLModel.metadata.tables["plaid_accounts"].c.limit.nullable is True


def test_generated_enums_are_stored_as_strings() -> None:
    """Store generated enum values as portable database strings."""
    user = User.from_api(user_object())
    manual_account = ManualAccount.from_api(manual_account_object())

    assert type(user.primary_currency) is str
    assert type(manual_account.type) is str
    assert isinstance(SQLModel.metadata.tables["users"].c.primary_currency.type, String)
    assert isinstance(SQLModel.metadata.tables["manual_accounts"].c.type.type, String)


def test_manual_account_metadata_remains_json_mapping() -> None:
    """Keep arbitrary manual-account metadata as a dictionary-backed JSON column."""
    record = ManualAccount.from_api(manual_account_object())

    assert isinstance(record.custom_metadata, dict)
    assert record.custom_metadata == {
        "source": "synthetic-fixture",
        "nested": {"version": 1},
    }
    assert isinstance(
        SQLModel.metadata.tables["manual_accounts"].c.custom_metadata.type, JSON
    )


def test_scalar_tables_are_registered() -> None:
    """Register all scalar record tables with SQLModel metadata."""
    assert {
        "users",
        "plaid_accounts",
        "manual_accounts",
        "tags",
    }.issubset(SQLModel.metadata.tables)


def test_scalar_timestamp_columns_are_native_and_retain_source_offsets() -> None:
    """Use portable native datetimes plus nullable source-offset state."""
    for record_type, field_names in TIMESTAMP_FIELDS_BY_RECORD.items():
        table = SQLModel.metadata.tables[TABLE_NAME_BY_RECORD[record_type]]
        for field_name in field_names:
            column_type = table.c[field_name].type
            assert isinstance(column_type, TypeDecorator)
            assert isinstance(column_type.impl, DateTime)
            assert column_type.impl.timezone is True
            assert table.c[f"{field_name}_offset_minutes"].nullable is True


def test_scalar_timestamp_tables_compile_for_postgresql() -> None:
    """Compile source-shape timestamp storage to PostgreSQL native columns."""
    for record_type in TIMESTAMP_FIELDS_BY_RECORD:
        table_name = TABLE_NAME_BY_RECORD[record_type]
        table = SQLModel.metadata.tables[table_name]

        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))

        assert f"CREATE TABLE {table_name}" in ddl
        assert "TIMESTAMP WITH TIME ZONE" in ddl
