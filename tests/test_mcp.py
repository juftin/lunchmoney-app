"""Tests for Model Context Protocol (MCP) tools and TOON encoding."""

import pytest
from fastmcp import FastMCP
import toons

from lunchmoney_mcp.mcp import register_mcp_tools


@pytest.fixture
def mcp_server() -> FastMCP[None]:
    """Provide a FastMCP server instance with registered tools."""
    server = FastMCP(name="Test MCP")
    register_mcp_tools(server)
    return server


@pytest.mark.asyncio
async def test_mcp_tools_registration(mcp_server: FastMCP[None]) -> None:
    """Verify all expected Lunch Money tools are registered on FastMCP server."""
    tools = await mcp_server.list_tools()
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
