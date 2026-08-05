"""Tests for the source-independent paginated transaction query service."""

import datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, create_autospec

import pytest

from database.factories import transaction_object
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Transaction
from lunchmoney_mcp.schemas import TransactionQuery
from lunchmoney_mcp.services import fetch_transactions


@pytest.mark.asyncio
async def test_live_transaction_query_forwards_filters_and_returns_all_results() -> (
    None
):
    """Use the paginating upstream client and return every matching transaction."""
    first = transaction_object(transaction_id=100, is_split_parent=False)
    second = transaction_object(transaction_id=101, is_split_parent=False).model_copy(
        update={"var_date": datetime.date(2026, 1, 2)}
    )
    refresh_transactions = AsyncMock(return_value={first.id: first, second.id: second})
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(refresh_transactions=refresh_transactions),
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)
    query = TransactionQuery(
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 1, 31),
        tag_id=21,
        include_children=True,
    )

    transactions = await fetch_transactions(
        client=client,
        db=database,
        query=query,
        live=True,
    )

    assert [transaction.id for transaction in transactions] == [
        first.id,
        second.id,
    ]
    refresh_transactions.assert_awaited_once_with(
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 1, 31),
        tag_id=21,
        include_children=True,
        cache=False,
    )


@pytest.mark.asyncio
async def test_persisted_transaction_query_applies_filters_and_returns_all_results() -> (
    None
):
    """Match the live query semantics against cached parent transaction objects."""
    older = transaction_object(transaction_id=100, is_split_parent=False).model_copy(
        update={"manual_account_id": 3}
    )
    newer = transaction_object(transaction_id=101, is_split_parent=False).model_copy(
        update={
            "var_date": datetime.date(2026, 1, 2),
            "manual_account_id": 3,
        }
    )
    excluded_pending = transaction_object(
        transaction_id=102,
        is_split_parent=False,
    ).model_copy(
        update={
            "var_date": datetime.date(2026, 1, 3),
            "manual_account_id": 3,
            "is_pending": True,
        }
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.list = AsyncMock(
        return_value=[
            Transaction.from_api(older),
            Transaction.from_api(newer),
            Transaction.from_api(excluded_pending),
        ]
    )
    query = TransactionQuery(manual_account_id=3)

    transactions = await fetch_transactions(
        client=create_autospec(LunchMoneyApp, instance=True),
        db=database,
        query=query,
        live=False,
    )
    assert [transaction.id for transaction in transactions] == [
        newer.id,
        older.id,
    ]
    assert database.list.await_args_list[0].args == (Transaction,)
