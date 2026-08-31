"""Tests for the source-independent paginated transaction query service."""

import datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import ANY, AsyncMock, create_autospec

import pytest

from database.factories import (
    category_object,
    child_transaction_object,
    manual_account_object,
    plaid_account_object,
    transaction_object,
)
from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import Transaction
from lunchmoney_app.schemas import (
    AccountsSummary,
    ReviewTransactionsQuery,
    TransactionQuery,
)
from lunchmoney_app.services import fetch_transactions, review_transactions


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
async def test_metadata_transaction_query_refreshes_from_lunch_money() -> None:
    """Fetch live records when the caller needs normally omitted Plaid metadata."""
    transaction = transaction_object(transaction_id=100, is_split_parent=False)
    refresh_transactions = AsyncMock(return_value={transaction.id: transaction})
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(refresh_transactions=refresh_transactions),
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)

    transactions = await fetch_transactions(
        client=client,
        db=database,
        query=TransactionQuery(status="unreviewed", include_metadata=True),
        live=False,
    )

    assert transactions == [transaction]
    refresh_transactions.assert_awaited_once_with(
        status="unreviewed",
        include_metadata=True,
        cache=False,
    )


@pytest.mark.asyncio
async def test_review_transactions_returns_linked_metadata_and_reference_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assemble a bounded review workspace without client-side identifier joins."""
    import lunchmoney_app.services.transactions as transactions_service

    transaction = transaction_object(is_split_parent=False).model_copy(
        update={"status": "unreviewed"}
    )
    category = category_object()
    plaid_account = plaid_account_object()
    manual_account = manual_account_object()
    fetch_transaction_records = AsyncMock(return_value=[transaction])
    fetch_category_records = AsyncMock(return_value=[category])
    fetch_account_records = AsyncMock(
        return_value=AccountsSummary(
            plaid_accounts=[plaid_account],
            manual_accounts=[manual_account],
        )
    )
    monkeypatch.setattr(
        transactions_service,
        "fetch_transactions",
        fetch_transaction_records,
    )
    monkeypatch.setattr(
        transactions_service,
        "fetch_categories",
        fetch_category_records,
    )
    monkeypatch.setattr(
        transactions_service,
        "fetch_accounts",
        fetch_account_records,
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)
    client = create_autospec(LunchMoneyApp, instance=True)
    query = ReviewTransactionsQuery(
        start_date=datetime.date(2026, 7, 16),
        end_date=datetime.date(2026, 8, 30),
    )

    result = await review_transactions(
        client=client,
        db=database,
        query=query,
        live=False,
    )

    assert result.start_date == query.start_date
    assert result.end_date == query.end_date
    assert result.categories == [category]
    assert result.accounts.plaid_accounts == [plaid_account]
    assert result.transactions[0].transaction == transaction
    assert result.transactions[0].category == category
    assert result.transactions[0].plaid_account == plaid_account
    assert result.transactions[0].manual_account is None
    fetch_transaction_records.assert_awaited_once_with(
        client=client,
        db=database,
        query=TransactionQuery(
            start_date=query.start_date,
            end_date=query.end_date,
            status="unreviewed",
            include_metadata=True,
        ),
        live=True,
    )
    fetch_category_records.assert_awaited_once_with(
        client=client,
        db=database,
        query=ANY,
        live=False,
    )
    assert fetch_category_records.await_args.kwargs["query"].format == "flattened"
    fetch_account_records.assert_awaited_once_with(db=database)


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


@pytest.mark.asyncio
async def test_persisted_transaction_query_includes_group_children_when_requested() -> (
    None
):
    """Include cached group children for the matching account only when requested."""
    group_child = child_transaction_object(
        transaction_id=101,
        split_parent_id=None,
        group_parent_id=100,
    )
    group_parent = Transaction.from_api(
        transaction_object(
            children=[group_child],
            is_split_parent=False,
            is_group_parent=True,
        )
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.list = AsyncMock(return_value=[group_parent, *group_parent.group_children])

    transactions = await fetch_transactions(
        client=create_autospec(LunchMoneyApp, instance=True),
        db=database,
        query=TransactionQuery(manual_account_id=3, include_group_children=True),
        live=False,
    )

    assert [transaction.id for transaction in transactions] == [group_child.id]
    assert transactions[0].group_parent_id == group_parent.id
    assert transactions[0].children is None
