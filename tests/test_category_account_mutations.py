"""Regression tests for Sprint 2 category and account mutations."""

import datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, create_autospec

import pytest
from lunchmoney.models import (
    CreateCategoryRequestObject,
    UpdateCategoryRequestObject,
)

from database.factories import (
    category_object,
    manual_account_object,
    transaction_object,
)
from lunchmoney_mcp.app.main import fastapi_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Category, ManualAccount, Transaction
from lunchmoney_mcp.mcp import mcp
from lunchmoney_mcp.schemas import (
    ManualAccountCreateRequest,
    ManualAccountUpdateRequest,
)
from lunchmoney_mcp.services import (
    create_category,
    create_manual_account,
    delete_category,
    delete_manual_account,
    trigger_plaid_fetch,
    update_category,
    update_manual_account,
)


def _category_create_request() -> CreateCategoryRequestObject:
    """Create a minimal valid category-create request."""
    return CreateCategoryRequestObject(name="Synthetic category")


def _manual_account_create_request() -> ManualAccountCreateRequest:
    """Create a minimal valid manual-account-create request."""
    return ManualAccountCreateRequest(
        name="Synthetic account",
        type="cash",
        balance="12.5000",
    )


@pytest.mark.asyncio
async def test_category_mutations_write_upstream_before_cache_updates() -> None:
    """Persist canonical category responses only after upstream writes succeed."""
    category = category_object()
    create = AsyncMock(return_value=category)
    update = AsyncMock(return_value=category)
    delete = AsyncMock()
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                categories=SimpleNamespace(
                    create_category=create,
                    update_category=update,
                    delete_category=delete,
                )
            )
        ),
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.list = AsyncMock(return_value=[])
    database.upsert = AsyncMock(side_effect=lambda record: record)
    database.delete = AsyncMock(return_value=True)
    create_request = _category_create_request()
    update_request = UpdateCategoryRequestObject(name="Updated category")

    created = await create_category(client=client, db=database, request=create_request)
    updated = await update_category(
        client=client,
        db=database,
        category_id=category.id,
        request=update_request,
    )
    await delete_category(
        client=client,
        db=database,
        category_id=category.id,
        force=True,
    )

    assert created.id == category.id
    assert updated.name == category.name
    create.assert_awaited_once_with(create_category_request_object=create_request)
    update.assert_awaited_once_with(
        id=category.id,
        update_category_request_object=update_request,
    )
    delete.assert_awaited_once_with(id=category.id, force=True)
    assert database.upsert.await_count == 2
    database.delete.assert_awaited_once_with(Category, category.id)


@pytest.mark.asyncio
async def test_manual_account_mutations_write_upstream_before_cache_updates() -> None:
    """Persist canonical manual-account responses only after upstream writes succeed."""
    account = manual_account_object()
    create = AsyncMock(return_value=account)
    update = AsyncMock(return_value=account)
    delete = AsyncMock()
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                manual_accounts=SimpleNamespace(
                    create_manual_account=create,
                    update_manual_account=update,
                    delete_manual_account=delete,
                )
            )
        ),
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.list = AsyncMock(return_value=[])
    database.upsert = AsyncMock(side_effect=lambda record: record)
    database.delete = AsyncMock(return_value=True)
    create_request = _manual_account_create_request()
    update_request = ManualAccountUpdateRequest(name="Updated account")

    created = await create_manual_account(
        client=client,
        db=database,
        request=create_request,
    )
    updated = await update_manual_account(
        client=client,
        db=database,
        account_id=account.id,
        request=update_request,
    )
    await delete_manual_account(
        client=client,
        db=database,
        account_id=account.id,
        delete_items=True,
        delete_balance_history=False,
    )

    assert created.id == account.id
    assert updated.name == account.name
    create.assert_awaited_once_with(
        create_manual_account_request_object=create_request.to_api(),
    )
    update.assert_awaited_once_with(
        id=account.id,
        update_manual_account_request_object=update_request.to_api(),
    )
    delete.assert_awaited_once_with(
        id=account.id,
        delete_items=True,
        delete_balance_history=False,
    )
    assert database.upsert.await_count == 2
    database.delete.assert_awaited_once_with(ManualAccount, account.id)


@pytest.mark.asyncio
async def test_deletes_reconcile_cached_transaction_relationships() -> None:
    """Clear or remove cached transaction links before deleting their owner."""
    category = category_object()
    account = manual_account_object()
    category_transaction = Transaction.from_api(transaction_object(tag_ids=[]))
    category_transaction.category_id = category.id
    account_transaction = Transaction.from_api(
        transaction_object(transaction_id=101, tag_ids=[])
    )
    account_transaction.manual_account_id = account.id
    account_transaction.plaid_account_id = None
    category_client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                categories=SimpleNamespace(delete_category=AsyncMock())
            )
        ),
    )
    account_client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                manual_accounts=SimpleNamespace(delete_manual_account=AsyncMock())
            )
        ),
    )
    category_database = create_autospec(LunchMoneyDatabase, instance=True)
    category_database.list = AsyncMock(return_value=[category_transaction])
    category_database.upsert_many = AsyncMock()
    category_database.delete = AsyncMock(return_value=True)
    account_database = create_autospec(LunchMoneyDatabase, instance=True)
    account_database.list = AsyncMock(return_value=[account_transaction])
    account_database.delete = AsyncMock(return_value=True)

    await delete_category(
        client=category_client,
        db=category_database,
        category_id=category.id,
    )
    await delete_manual_account(
        client=account_client,
        db=account_database,
        account_id=account.id,
        delete_items=True,
    )

    assert category_transaction.category_id is None
    category_database.upsert_many.assert_awaited_once_with([category_transaction])
    category_database.delete.assert_awaited_once_with(Category, category.id)
    account_database.delete.assert_any_await(Transaction, account_transaction.id)
    account_database.delete.assert_any_await(ManualAccount, account.id)


@pytest.mark.asyncio
async def test_plaid_fetch_forwards_its_optional_scope() -> None:
    """Forward optional Plaid fetch scope without touching the local cache."""
    trigger = AsyncMock()
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                plaid=SimpleNamespace(trigger_plaid_account_fetch=trigger)
            )
        ),
    )
    start_date = datetime.date(2026, 1, 1)
    end_date = datetime.date(2026, 1, 31)

    await trigger_plaid_fetch(
        client=client,
        start_date=start_date,
        end_date=end_date,
        account_id=42,
    )

    trigger.assert_awaited_once_with(start_date=start_date, end_date=end_date, id=42)


def test_mutation_routes_are_registered() -> None:
    """Publish every Sprint 2 REST endpoint in the generated OpenAPI document."""
    paths = fastapi_app.openapi()["paths"]

    assert {"post"} <= set(paths["/categories"])
    assert {"put", "delete"} <= set(paths["/categories/{category_id}"])
    assert {"post"} <= set(paths["/accounts/manual"])
    assert {"put", "delete"} <= set(paths["/accounts/manual/{account_id}"])
    assert {"post"} <= set(paths["/accounts/plaid/sync"])


@pytest.mark.asyncio
async def test_mutation_mcp_tools_are_registered() -> None:
    """Publish every Sprint 2 mutation tool on the shared FastMCP instance."""
    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert {
        "create_category",
        "update_category",
        "delete_category",
        "create_manual_account",
        "update_manual_account",
        "delete_manual_account",
        "trigger_plaid_fetch",
    } <= tool_names
