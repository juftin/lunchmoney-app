"""Tests for scalar SQLModel records and generated API conversions."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any, Protocol

import pytest
from pydantic import BaseModel
from sqlalchemy import JSON, Numeric, String
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
    """Declare one SQLModel field for every generated scalar API field."""
    assert set(record_type.model_fields) == set(api_type.model_fields)


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
