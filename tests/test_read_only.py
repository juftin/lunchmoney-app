"""Regression tests for Sprint 1 read-only services and registrations."""

import datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, create_autospec

import pytest
from lunchmoney.models import (
    CategoryObject,
    RecurringObject,
    SummaryResponseObject,
)

from database.factories import (
    category_object,
    manual_account_object,
    plaid_account_object,
    tag_object,
    transaction_object,
)
from lunchmoney_mcp.app.main import fastapi_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import (
    Category,
    ManualAccount,
    PlaidAccount,
    Tag,
    Transaction,
)
from lunchmoney_mcp.mcp import mcp
from lunchmoney_mcp.schemas import CategoryQuery
from lunchmoney_mcp.services import (
    fetch_account_summary,
    fetch_accounts,
    fetch_category_by_id,
    fetch_categories,
    fetch_manual_account_by_id,
    fetch_manual_accounts,
    fetch_plaid_account_by_id,
    fetch_plaid_accounts,
    fetch_recurring_item_by_id,
    fetch_recurring_items,
    fetch_tag_by_id,
    fetch_tags,
    fetch_transaction_by_id,
)


def _recurring_item() -> RecurringObject:
    """Create one minimal valid recurring-item response for live-query tests."""
    return RecurringObject.model_validate(
        {
            "id": 81,
            "description": "Synthetic recurring item",
            "status": "reviewed",
            "transaction_criteria": {
                "start_date": None,
                "end_date": None,
                "granularity": "month",
                "quantity": 1,
                "anchor_date": "2026-01-01",
                "payee": "Synthetic subscription",
                "amount": "12.0000",
                "to_base": 12,
                "currency": "usd",
                "plaid_account_id": None,
                "manual_account_id": None,
            },
            "overrides": {"payee": None, "notes": None, "category_id": None},
            "matches": None,
            "created_by": 1,
            "created_at": "2026-01-01T12:00:00Z",
            "updated_at": "2026-01-01T12:00:00Z",
            "source": "manual",
        }
    )


@pytest.mark.asyncio
async def test_summary_service_reads_period_snapshot() -> None:
    """Read a summary snapshot using its synchronized transaction period."""
    summary = SummaryResponseObject.model_validate({"aligned": True, "categories": []})
    database = AsyncMock()
    database.get_cached_response.return_value = summary.model_dump(mode="json")
    client = create_autospec(LunchMoneyApp, instance=True)

    result = await fetch_account_summary(
        db=database,
        client=client,
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 1, 31),
        include_exclude_from_budgets=True,
        include_occurrences=True,
        include_past_budget_dates=True,
        include_totals=True,
        include_rollover_pool=True,
    )

    assert result == summary
    database.get_cached_response.assert_awaited_once_with(
        "summary:2026-01-01:2026-01-31"
    )


@pytest.mark.asyncio
async def test_recurring_services_read_period_snapshot() -> None:
    """Read recurring items and single items from a period snapshot."""
    recurring_item = _recurring_item()
    database = AsyncMock()
    database.get_cached_response.return_value = {
        "items": [recurring_item.model_dump(mode="json")]
    }
    client = create_autospec(LunchMoneyApp, instance=True)
    start_date = datetime.date(2026, 1, 1)
    end_date = datetime.date(2026, 1, 31)

    listed = await fetch_recurring_items(
        db=database,
        client=client,
        start_date=start_date,
        end_date=end_date,
        include_suggested=True,
    )
    selected = await fetch_recurring_item_by_id(
        db=database,
        client=client,
        recurring_item_id=recurring_item.id,
        start_date=start_date,
        end_date=end_date,
    )

    assert listed == [recurring_item]
    assert selected == recurring_item
    database.get_cached_response.assert_awaited_with("recurring:2026-01-01:2026-01-31")


@pytest.mark.asyncio
async def test_recurring_service_filters_suggested_items_by_default() -> None:
    """Return suggested recurring items only when the caller explicitly requests them."""
    recurring_item = _recurring_item()
    suggested = recurring_item.model_copy(update={"id": 82, "status": "suggested"})
    database = AsyncMock()
    database.get_cached_response.return_value = {
        "items": [
            recurring_item.model_dump(mode="json"),
            suggested.model_dump(mode="json"),
        ]
    }
    client = create_autospec(LunchMoneyApp, instance=True)

    default_items = await fetch_recurring_items(db=database, client=client)
    all_items = await fetch_recurring_items(
        db=database, client=client, include_suggested=True
    )

    assert default_items == [recurring_item]
    assert all_items == [recurring_item, suggested]
    database.get_cached_response.assert_awaited_with("recurring:latest")


@pytest.mark.asyncio
async def test_recurring_service_refreshes_a_missing_requested_window() -> None:
    """Fetch and cache a requested recurring window absent from synchronized snapshots."""
    recurring_item = _recurring_item()
    get_all_recurring = AsyncMock(
        return_value=SimpleNamespace(recurring_items=[recurring_item])
    )
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                recurring_items=SimpleNamespace(get_all_recurring=get_all_recurring)
            )
        ),
    )
    database = AsyncMock()
    database.get_cached_response.return_value = None
    start_date = datetime.date(2025, 1, 1)

    result = await fetch_recurring_items(
        db=database,
        client=client,
        start_date=start_date,
    )

    assert result == [recurring_item]
    get_all_recurring.assert_awaited_once_with(
        start_date=start_date,
        end_date=None,
        include_suggested=True,
    )
    database.upsert_cached_response.assert_awaited_once_with(
        "recurring:2025-01-01:None",
        {"items": [recurring_item.model_dump(mode="json")]},
    )


@pytest.mark.asyncio
async def test_summary_service_refreshes_a_missing_requested_window() -> None:
    """Fetch and cache a requested summary window absent from synchronized snapshots."""
    summary = SummaryResponseObject.model_validate({"aligned": True, "categories": []})
    get_budget_summary = AsyncMock(return_value=summary)
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                summary=SimpleNamespace(get_budget_summary=get_budget_summary)
            ),
            refresh=AsyncMock(return_value={}),
        ),
    )
    database = AsyncMock()
    database.get_cached_response.return_value = None
    database.list.return_value = []
    start_date = datetime.date(2025, 1, 1)
    end_date = datetime.date(2025, 1, 31)

    result = await fetch_account_summary(
        db=database,
        client=client,
        start_date=start_date,
        end_date=end_date,
    )

    assert result.aligned is True
    get_budget_summary.assert_awaited_once_with(
        start_date=start_date,
        end_date=end_date,
        include_exclude_from_budgets=True,
        include_occurrences=True,
        include_past_budget_dates=True,
        include_totals=True,
        include_rollover_pool=True,
    )


@pytest.mark.asyncio
async def test_summary_service_refreshes_categories_before_filtering_a_new_snapshot() -> (
    None
):
    """Exclude budget-hidden categories from a newly fetched summary snapshot."""
    category = category_object()
    summary = SummaryResponseObject.model_validate(
        {
            "aligned": True,
            "categories": [
                {
                    "category_id": category.id,
                    "totals": {
                        "other_activity": 0,
                        "recurring_activity": 0,
                        "budgeted": 0,
                        "available": 0,
                        "recurring_remaining": 0,
                        "recurring_expected": 0,
                    },
                }
            ],
        }
    )
    get_budget_summary = AsyncMock(return_value=summary)
    refresh = AsyncMock(return_value={category.id: category})
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                summary=SimpleNamespace(get_budget_summary=get_budget_summary)
            ),
            refresh=refresh,
        ),
    )
    database = AsyncMock()
    database.get_cached_response.return_value = None
    database.list.return_value = [Category.from_api(category)]

    result = await fetch_account_summary(
        db=database,
        client=client,
        start_date=datetime.date(2025, 1, 1),
        end_date=datetime.date(2025, 1, 31),
    )

    assert result.categories == []
    refresh.assert_awaited_once_with(model=CategoryObject, cache=False)
    database.upsert_many.assert_awaited_once_with([Category.from_api(category)])


@pytest.mark.asyncio
async def test_synchronized_tag_services_map_records_and_missing_items() -> None:
    """Expose complete synchronized tags and preserve a missing result."""
    tag = Tag.from_api(tag_object())
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.list = AsyncMock(return_value=[tag])
    database.get = AsyncMock(side_effect=[tag, None])

    listed = await fetch_tags(db=database)
    selected = await fetch_tag_by_id(db=database, tag_id=tag.id)
    missing = await fetch_tag_by_id(db=database, tag_id=999)

    assert listed[0].model_dump(mode="json") == tag_object().model_dump(mode="json")
    assert selected is not None
    assert selected.model_dump(mode="json") == tag_object().model_dump(mode="json")
    assert missing is None
    database.list.assert_awaited_once_with(Tag)
    assert database.get.await_args_list[0].args == (Tag, tag.id)


@pytest.mark.asyncio
async def test_synchronized_single_item_services_map_all_domain_records() -> None:
    """Expose complete synchronized category, account, and transaction records."""
    category_api = category_object()
    manual_account_api = manual_account_object()
    plaid_account_api = plaid_account_object()
    transaction_api = transaction_object(tag_ids=[])
    category = Category.from_api(category_api)
    manual_account = ManualAccount.from_api(manual_account_api)
    plaid_account = PlaidAccount.from_api(plaid_account_api)
    transaction = Transaction.from_api(transaction_api)
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.get = AsyncMock(
        side_effect=[category, manual_account, plaid_account, transaction]
    )

    category_result = await fetch_category_by_id(db=database, category_id=category.id)
    manual_result = await fetch_manual_account_by_id(
        db=database,
        account_id=manual_account.id,
    )
    plaid_result = await fetch_plaid_account_by_id(
        db=database,
        account_id=plaid_account.id,
    )
    transaction_result = await fetch_transaction_by_id(
        db=database,
        transaction_id=transaction.id,
    )

    assert category_result is not None
    assert category_result.model_dump(mode="json") == category_api.model_dump(
        mode="json"
    )
    assert manual_result is not None
    assert manual_result.model_dump(mode="json") == manual_account_api.model_dump(
        mode="json"
    )
    assert plaid_result is not None
    assert plaid_result.model_dump(mode="json") == plaid_account_api.model_dump(
        mode="json"
    )
    assert transaction_result is not None
    assert transaction_result.model_dump(mode="json") == transaction_api.model_dump(
        mode="json"
    )
    assert database.get.await_args_list[0].args == (Category, category.id)
    assert database.get.await_args_list[1].args == (ManualAccount, manual_account.id)
    assert database.get.await_args_list[2].args == (PlaidAccount, plaid_account.id)
    assert database.get.await_args_list[3].args == (Transaction, transaction.id)


@pytest.mark.asyncio
async def test_synchronized_collection_services_preserve_complete_api_objects() -> None:
    """Return full upstream models rather than locally reduced list summaries."""
    category_api = category_object()
    manual_account_api = manual_account_object()
    plaid_account_api = plaid_account_object()
    category = Category.from_api(category_api)
    manual_account = ManualAccount.from_api(manual_account_api)
    plaid_account = PlaidAccount.from_api(plaid_account_api)
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.list = AsyncMock(
        side_effect=[[category], [manual_account], [plaid_account]]
    )

    categories = await fetch_categories(
        client=create_autospec(LunchMoneyApp, instance=True),
        db=database,
        query=CategoryQuery(),
        live=False,
    )
    manual_accounts = await fetch_manual_accounts(db=database)
    plaid_accounts = await fetch_plaid_accounts(db=database)

    assert categories[0].model_dump(mode="json") == category_api.model_dump(mode="json")
    assert manual_accounts[0].model_dump(mode="json") == manual_account_api.model_dump(
        mode="json"
    )
    assert plaid_accounts[0].model_dump(mode="json") == plaid_account_api.model_dump(
        mode="json"
    )
    assert database.list.await_args_list[0].args == (Category,)
    assert database.list.await_args_list[1].args == (ManualAccount,)
    assert database.list.await_args_list[2].args == (PlaidAccount,)


@pytest.mark.asyncio
async def test_shared_accounts_service_preserves_complete_source_collections() -> None:
    """Return both complete account collections in the shared response envelope."""
    manual_account_api = manual_account_object()
    plaid_account_api = plaid_account_object()
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.list = AsyncMock(
        side_effect=[
            [ManualAccount.from_api(manual_account_api)],
            [PlaidAccount.from_api(plaid_account_api)],
        ]
    )

    accounts = await fetch_accounts(db=database)

    assert accounts.manual_accounts[0].model_dump(mode="json") == (
        manual_account_api.model_dump(mode="json")
    )
    assert accounts.plaid_accounts[0].model_dump(mode="json") == (
        plaid_account_api.model_dump(mode="json")
    )
    assert database.list.await_args_list[0].args == (ManualAccount,)
    assert database.list.await_args_list[1].args == (PlaidAccount,)


def test_read_only_routes_are_registered() -> None:
    """Publish every Sprint 1 REST endpoint in the generated OpenAPI document."""
    paths = fastapi_app.openapi()["paths"]

    assert "/api/summary" in paths
    assert "/api/tags" in paths
    assert "/api/tags/{tag_id}" in paths
    assert "/api/recurring_items" in paths
    assert "/api/recurring_items/{recurring_item_id}" in paths
    assert "/api/categories/{category_id}" in paths
    assert "/api/manual_accounts" in paths
    assert "/api/plaid_accounts" in paths
    assert "/api/accounts" in paths
    assert "/api/manual_accounts/{id}" in paths
    assert "/api/plaid_accounts/{id}" in paths
    assert "/api/transactions/{transaction_id}" in paths


@pytest.mark.asyncio
async def test_read_only_mcp_tools_are_registered() -> None:
    """Publish every Sprint 1 MCP tool on the shared FastMCP instance."""
    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert {
        "list_accounts",
        "get_account_summary",
        "list_tags",
        "get_tag",
        "list_recurring_items",
        "get_recurring_item",
        "get_category",
        "get_manual_account",
        "get_plaid_account",
        "get_transaction",
    } <= tool_names
