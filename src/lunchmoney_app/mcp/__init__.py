"""Model Context Protocol (MCP) server integration package."""

from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.mcp.tools.accounts import (
    get_manual_account,
    get_plaid_account,
    list_accounts,
    list_manual_accounts,
    list_plaid_accounts,
)
from lunchmoney_app.mcp.tools.categories import get_category, list_categories
from lunchmoney_app.mcp.tools.recurring import get_recurring_item, list_recurring_items
from lunchmoney_app.mcp.tools.spending import get_category_spending
from lunchmoney_app.mcp.tools.summary import get_account_summary
from lunchmoney_app.mcp.tools.sync import sync_data
from lunchmoney_app.mcp.tools.tags import get_tag, list_tags
from lunchmoney_app.mcp.tools.transactions import (
    bulk_delete_transactions,
    bulk_update_transactions,
    create_transactions,
    delete_attachment,
    delete_transaction,
    get_attachment,
    list_transactions,
    get_transaction,
    group_transactions,
    split_transaction,
    ungroup_transactions,
    unsplit_transaction,
    update_transaction,
    upload_attachment,
)
from lunchmoney_app.mcp.tools.user import get_user_info
from lunchmoney_app.mcp import server as _server

_ = _server

__all__ = [
    "get_account_summary",
    "bulk_delete_transactions",
    "bulk_update_transactions",
    "create_transactions",
    "delete_attachment",
    "delete_transaction",
    "get_attachment",
    "get_category_spending",
    "get_category",
    "get_manual_account",
    "get_plaid_account",
    "list_transactions",
    "get_recurring_item",
    "get_tag",
    "get_transaction",
    "group_transactions",
    "get_user_info",
    "list_manual_accounts",
    "list_accounts",
    "list_plaid_accounts",
    "list_categories",
    "list_recurring_items",
    "list_tags",
    "mcp",
    "sync_data",
    "split_transaction",
    "ungroup_transactions",
    "unsplit_transaction",
    "update_transaction",
    "upload_attachment",
]
