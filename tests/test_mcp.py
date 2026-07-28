"""Tests for Model Context Protocol (MCP) tools and capabilities."""

import pytest
from fastmcp import FastMCP

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
