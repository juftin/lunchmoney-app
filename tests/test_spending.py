"""Tests for grouped category spending service, endpoint, and MCP tool."""

from collections.abc import AsyncIterator
import datetime
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from starlette.testclient import TestClient
from unittest.mock import create_autospec

from database.factories import (
    category_object,
    child_category_object,
    transaction_object,
)
from lunchmoney_app.app import app as fastapi_app
from lunchmoney_app.database import LunchMoneyDatabase, run_migrations
from lunchmoney_app.database.models import Category, Transaction
from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.mcp import mcp
from lunchmoney_app.services import fetch_category_spending
from lunchmoney_app.services.operations import StatefulOperationContextFactory


@pytest_asyncio.fixture
async def database(tmp_path: Path) -> AsyncIterator[LunchMoneyDatabase]:
    """Provide an initialized SQLite database for spending tests."""
    db_path = tmp_path / "spending.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    await run_migrations(db_url)
    async with LunchMoneyDatabase(db_url) as db:
        yield db


@pytest.mark.asyncio
async def test_fetch_category_spending(
    database: LunchMoneyDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify category spending aggregation and parent/child rollups."""
    today = datetime.date.today()

    child_api = child_category_object().model_copy(
        update={"id": 20, "name": "Restaurants", "group_id": 10, "is_income": False}
    )
    parent_api = category_object(children=[child_api]).model_copy(
        update={"id": 10, "name": "Food & Dining", "is_group": True, "is_income": False}
    )

    parent_cat = Category.from_api(parent_api)
    child_cat = parent_cat.children[0]
    await database.upsert(parent_cat)
    await database.upsert(child_cat)

    txn1_api = transaction_object().model_copy(
        update={
            "id": 101,
            "date": today - datetime.timedelta(days=2),
            "var_date": today - datetime.timedelta(days=2),
            "amount": Decimal("45.50"),
            "payee": "Local Bistro",
            "category_id": 20,
            "plaid_account_id": None,
            "manual_account_id": None,
            "tags": [],
            "tag_ids": [],
            "is_split_parent": False,
            "split_parent_id": None,
        }
    )
    txn2_api = transaction_object().model_copy(
        update={
            "id": 102,
            "date": today - datetime.timedelta(days=5),
            "var_date": today - datetime.timedelta(days=5),
            "amount": Decimal("15.00"),
            "payee": "Coffee Shop",
            "category_id": 10,
            "plaid_account_id": None,
            "manual_account_id": None,
            "tags": [],
            "tag_ids": [],
            "is_split_parent": False,
            "split_parent_id": None,
        }
    )
    txn1 = Transaction.from_api(txn1_api)
    txn2 = Transaction.from_api(txn2_api)
    await database.upsert(txn1)
    await database.upsert(txn2)

    database_list = database.list

    async def bounded_list(model: type[Category] | type[Transaction]) -> list[object]:
        """Require analytics transactions to use their date-bounded SQL path."""
        if model is Transaction:
            raise AssertionError("analytics loaded every transaction")
        return await database_list(model)  # type: ignore[arg-type]

    monkeypatch.setattr(database, "list", bounded_list)

    async with StatefulOperationContextFactory(
        create_autospec(LunchMoneyApp, instance=True), database
    ).operation() as context:
        response = await fetch_category_spending(context, days=30)
    assert response.total_spending == 60.50
    assert len(response.categories) == 1

    parent_spending = response.categories[0]
    assert parent_spending.category_id == 10
    assert parent_spending.category_name == "Food & Dining"
    assert parent_spending.total_amount == 60.50
    assert parent_spending.transaction_count == 2
    assert len(parent_spending.children) == 1

    child_spending = parent_spending.children[0]
    assert child_spending.category_id == 20
    assert child_spending.category_name == "Restaurants"
    assert child_spending.total_amount == 45.50
    assert child_spending.transaction_count == 1


@pytest.mark.asyncio
async def test_stateful_recent_transactions_applies_sql_limit(
    database: LunchMoneyDatabase,
) -> None:
    """Load only the requested dashboard transaction count from SQL."""
    today = datetime.date.today()
    for transaction_id in range(100, 106):
        await database.upsert(
            Transaction.from_api(
                transaction_object(
                    transaction_id=transaction_id,
                    is_split_parent=False,
                ).model_copy(
                    update={
                        "var_date": today,
                        "category_id": None,
                        "plaid_account_id": None,
                        "manual_account_id": None,
                        "tags": [],
                        "tag_ids": [],
                    }
                )
            )
        )

    async with StatefulOperationContextFactory(
        create_autospec(LunchMoneyApp, instance=True), database
    ).operation() as context:
        transactions = await context.transactions.recent(
            start_date=today,
            end_date=today,
            limit=3,
        )

    assert [transaction.id for transaction in transactions] == [105, 104, 103]


def test_fastapi_spending_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GET /api/spending/category endpoint returns 200."""
    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "mock-token")

    with TestClient(fastapi_app, base_url="http://localhost") as client:
        response = client.get("/api/spending/category?days=30")
        assert response.status_code == 200
        data = response.json()
        assert "total_spending" in data
        assert "total_income" in data
        assert "categories" in data


@pytest.mark.asyncio
async def test_mcp_spending_tool_registration() -> None:
    """Verify get_category_spending tool is registered on FastMCP server."""
    tools = await mcp.list_tools()
    tool_names = {t.name for t in tools}
    assert "get_category_spending" in tool_names
