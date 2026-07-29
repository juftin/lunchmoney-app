"""Tests for grouped category spending service, endpoint, and MCP tool."""

from collections.abc import AsyncIterator
import datetime
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from starlette.testclient import TestClient

from database.factories import (
    category_object,
    child_category_object,
    transaction_object,
)
from lunchmoney_mcp.app import app as fastapi_app
from lunchmoney_mcp.database import LunchMoneyDatabase, run_migrations
from lunchmoney_mcp.database.models import Category, Transaction
from lunchmoney_mcp.mcp import mcp
from lunchmoney_mcp.services import fetch_category_spending


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

    response = await fetch_category_spending(db=database, days=30)
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


def test_fastapi_spending_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GET /spending/category endpoint returns 200."""
    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "mock-token")

    with TestClient(fastapi_app) as client:
        response = client.get("/spending/category?days=30")
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
