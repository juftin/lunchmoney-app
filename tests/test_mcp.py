"""Tests for Model Context Protocol (MCP) tools and Pydantic response models."""

import sys
from unittest.mock import ANY, AsyncMock

import pytest

from lunchmoney_mcp.mcp import mcp
from lunchmoney_mcp.schemas import (
    CategoryInfo,
    RootResponse,
    SyncDetails,
    SyncResponse,
    SyncResult,
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


@pytest.mark.asyncio
async def test_mcp_sync_tool_forwards_incremental_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward incremental tool arguments unchanged to the sync service."""
    sync_tool_module = sys.modules["lunchmoney_mcp.mcp.tools.sync"]
    mock_execute_mcp_sync = AsyncMock(
        return_value=SyncResult(
            synced_records=SyncDetails(
                user=0,
                plaid_accounts=0,
                manual_accounts=0,
                categories=0,
                tags=0,
                transactions=0,
                total=0,
            )
        )
    )
    monkeypatch.setattr(sync_tool_module, "execute_mcp_sync", mock_execute_mcp_sync)
    monkeypatch.setattr(sync_tool_module, "get_database", object)
    monkeypatch.setattr(sync_tool_module, "get_lunchmoney_app", object)

    await mcp.call_tool(
        "sync_data",
        {
            "days": 14,
            "incremental": True,
            "safety_margin_minutes": 9,
        },
    )

    mock_execute_mcp_sync.assert_awaited_once_with(
        db=ANY,
        client=ANY,
        days=14,
        incremental=True,
        safety_margin_minutes=9,
    )


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
