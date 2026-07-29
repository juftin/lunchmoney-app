"""Model Context Protocol (MCP) server integration package."""

from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.mcp.tools.accounts import list_accounts
from lunchmoney_mcp.mcp.tools.categories import list_categories
from lunchmoney_mcp.mcp.tools.spending import get_category_spending
from lunchmoney_mcp.mcp.tools.sync import sync_data
from lunchmoney_mcp.mcp.tools.transactions import get_recent_transactions
from lunchmoney_mcp.mcp.tools.user import get_user_info

__all__ = [
    "get_category_spending",
    "get_recent_transactions",
    "get_user_info",
    "list_accounts",
    "list_categories",
    "mcp",
    "sync_data",
]
