"""FastMCP tools for live Lunch Money budget settings queries."""

from typing import TYPE_CHECKING

import datetime

from lunchmoney.models import (
    BudgetSettingsResponseObject,
    BudgetUpsertResponseObject,
    UpsertBudgetRequestObject,
)

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.services import (
    clear_budget_value,
    fetch_budget_settings,
    set_budget_value,
)

if TYPE_CHECKING:
    from lunchmoney_mcp.client import LunchMoneyApp


@mcp.tool()
async def get_budget_settings() -> BudgetSettingsResponseObject | None:
    """Fetch the authenticated user's budget-period settings.

    Returns
    -------
    BudgetSettingsResponseObject
        Upstream budget-period settings.
    """
    return await fetch_budget_settings(db=get_database())


@mcp.tool()
async def upsert_budget(
    request: UpsertBudgetRequestObject,
) -> BudgetUpsertResponseObject:
    """Set one category's budget value for a budget period."""
    client: LunchMoneyApp = get_lunchmoney_app()
    return await set_budget_value(client=client, request=request)


@mcp.tool()
async def clear_budget(
    category_id: int,
    start_date: datetime.date,
) -> None:
    """Clear one category's budget value for a budget period."""
    client: LunchMoneyApp = get_lunchmoney_app()
    await clear_budget_value(
        client=client,
        category_id=category_id,
        start_date=start_date,
    )
