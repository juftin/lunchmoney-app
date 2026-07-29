"""Services package containing reusable domain business logic."""

from lunchmoney_mcp.services.accounts import (
    create_manual_account,
    delete_manual_account,
    fetch_accounts,
    fetch_manual_account_by_id,
    fetch_plaid_account_by_id,
    trigger_plaid_fetch,
    update_manual_account,
)
from lunchmoney_mcp.services.categories import (
    create_category,
    delete_category,
    fetch_categories,
    fetch_category_by_id,
    update_category,
)
from lunchmoney_mcp.services.recurring import (
    fetch_recurring_item_by_id,
    fetch_recurring_items,
)
from lunchmoney_mcp.services.spending import fetch_category_spending
from lunchmoney_mcp.services.summary import fetch_account_summary
from lunchmoney_mcp.services.sync import execute_mcp_sync, execute_sync
from lunchmoney_mcp.services.tags import fetch_tag_by_id, fetch_tags
from lunchmoney_mcp.services.transactions import (
    fetch_recent_transactions,
    fetch_transaction_by_id,
)
from lunchmoney_mcp.services.user import fetch_user_info

__all__ = [
    "execute_mcp_sync",
    "execute_sync",
    "fetch_account_summary",
    "fetch_accounts",
    "fetch_categories",
    "fetch_category_by_id",
    "fetch_category_spending",
    "fetch_manual_account_by_id",
    "fetch_plaid_account_by_id",
    "fetch_recent_transactions",
    "fetch_recurring_item_by_id",
    "fetch_recurring_items",
    "fetch_tag_by_id",
    "fetch_tags",
    "fetch_transaction_by_id",
    "fetch_user_info",
    "create_category",
    "update_category",
    "delete_category",
    "create_manual_account",
    "update_manual_account",
    "delete_manual_account",
    "trigger_plaid_fetch",
]
