"""Tests for Model Context Protocol (MCP) tools and Pydantic response models."""

import pytest

from lunchmoney_mcp.mcp import mcp
from lunchmoney_mcp.schemas import (
    CategoryInfo,
    RootResponse,
    SyncDetails,
    SyncResponse,
    UserInfo,
)


@pytest.mark.asyncio
async def test_mcp_tools_registration() -> None:
    """Verify all expected Lunch Money tools are registered on top-level FastMCP server."""
    tools = await mcp.list_tools()
    tool_names = {t.name for t in tools}

    assert "sync_data" in tool_names
    assert "get_user_info" in tool_names
    assert "list_categories" in tool_names
    assert "list_accounts" in tool_names
    assert "get_recent_transactions" in tool_names


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
