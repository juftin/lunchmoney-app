"""Central FastMCP application instance definition for Lunch Money operations."""

from fastmcp import FastMCP

mcp: FastMCP[None] = FastMCP("Lunch Money MCP")
"""Application-wide FastMCP server instance."""
