"""Tests for Model Context Protocol (MCP) tools generated from FastAPI routes."""

import pytest

from lunchmoney_mcp.app import mcp
from lunchmoney_mcp.schemas import (
    CategoryInfo,
    RootResponse,
    SyncDetails,
    SyncResponse,
    UserInfo,
)


@pytest.mark.asyncio
async def test_mcp_tools_generated_from_fastapi() -> None:
    """Verify FastAPI routes are automatically registered as MCP tools."""
    tools = await mcp.list_tools()
    tool_names = {t.name for t in tools}

    assert len(tool_names) > 0


def test_pydantic_models() -> None:
    """Verify Pydantic models instantiate and validate correctly."""
    user = UserInfo(
        id=1,
        name="Test User",
        email="test@example.com",
        budget_name="My Budget",
        primary_currency="usd",
    )
    assert user.id == 1
    assert user.primary_currency == "usd"

    cat = CategoryInfo(
        id=10,
        name="Groceries",
        is_income=False,
        exclude_from_budget=False,
        exclude_from_totals=False,
        is_group=False,
    )
    assert cat.name == "Groceries"

    root_resp = RootResponse()
    assert root_resp.message == "Hello World"

    sync_resp = SyncResponse(
        message="Synchronization complete",
        synced=SyncDetails(
            user=1,
            plaid_accounts=2,
            manual_accounts=3,
            categories=4,
            tags=5,
            transactions=6,
            total=21,
        ),
    )
    assert sync_resp.synced.total == 21
