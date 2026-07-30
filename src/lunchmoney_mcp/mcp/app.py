"""Central FastMCP application instance definition for Lunch Money operations."""

from fastmcp import FastMCP

from lunchmoney_mcp.app.auth import get_mcp_oauth_provider

mcp: FastMCP[None] = FastMCP("Lunch Money MCP", auth=get_mcp_oauth_provider())
"""Application-wide FastMCP server instance."""
