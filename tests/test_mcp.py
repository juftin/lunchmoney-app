"""Tests for Model Context Protocol (MCP) tools and TOON encoding."""

import pytest
import toons

from lunchmoney_mcp.mcp import mcp


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
async def test_mcp_toons_serialization() -> None:
    """Verify toons properly serializes structured objects."""
    data = [{"id": 1, "name": "Groceries", "amount": 42.5}]
    toon_output = toons.dumps(data)

    assert "Groceries" in toon_output
    assert "42.5" in toon_output
