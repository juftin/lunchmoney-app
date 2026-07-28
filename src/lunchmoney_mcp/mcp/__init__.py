"""Model Context Protocol (MCP) server integration package."""

from lunchmoney_mcp.mcp.server import (
    AccountInfo,
    AccountsSummary,
    CategoryInfo,
    SyncResult,
    TransactionInfo,
    UserInfo,
    get_recent_transactions,
    get_user_info,
    list_accounts,
    list_categories,
    mcp,
    sync_data,
)

__all__ = [
    "AccountInfo",
    "AccountsSummary",
    "CategoryInfo",
    "SyncResult",
    "TransactionInfo",
    "UserInfo",
    "get_recent_transactions",
    "get_user_info",
    "list_accounts",
    "list_categories",
    "mcp",
    "sync_data",
]
