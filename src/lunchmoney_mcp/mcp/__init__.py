"""Model Context Protocol (MCP) server integration package."""

from lunchmoney_mcp.mcp.server import (
    get_recent_transactions,
    get_user_info,
    list_accounts,
    list_categories,
    mcp,
    sync_data,
)

__all__ = [
    "get_recent_transactions",
    "get_user_info",
    "list_accounts",
    "list_categories",
    "mcp",
    "sync_data",
]
