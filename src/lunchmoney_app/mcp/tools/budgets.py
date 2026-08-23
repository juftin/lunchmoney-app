"""FastMCP budget tools."""

import datetime

from lunchmoney.models import (
    BudgetSettingsResponseObject,
    BudgetUpsertResponseObject,
    UpsertBudgetRequestObject,
)

from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.services import (
    clear_budget_value,
    fetch_budget_settings,
    set_budget_value,
)
from lunchmoney_app.services.operations import get_operation_context


@mcp.tool()
async def get_budget_settings() -> BudgetSettingsResponseObject:
    """Return budget-period settings."""
    return await fetch_budget_settings(get_operation_context())


@mcp.tool()
async def upsert_budget(
    request: UpsertBudgetRequestObject,
) -> BudgetUpsertResponseObject:
    """Set one category's budget value."""
    return await set_budget_value(get_operation_context(), request)


@mcp.tool()
async def clear_budget(category_id: int, start_date: datetime.date) -> None:
    """Clear one category's budget value."""
    await clear_budget_value(get_operation_context(), category_id, start_date)


__all__ = ["clear_budget", "get_budget_settings", "upsert_budget"]
