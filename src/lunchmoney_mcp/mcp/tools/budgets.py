"""FastMCP tools for live Lunch Money budget settings queries."""

from typing import TYPE_CHECKING

from lunchmoney.models import BudgetSettingsResponseObject

from lunchmoney_mcp.app.dependencies import get_lunchmoney_app
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.services import fetch_budget_settings

if TYPE_CHECKING:
    from lunchmoney_mcp.client import LunchMoneyApp


@mcp.tool()
async def get_budget_settings() -> BudgetSettingsResponseObject:
    """Fetch the authenticated user's budget-period settings.

    Returns
    -------
    BudgetSettingsResponseObject
        Upstream budget-period settings.
    """
    client: LunchMoneyApp = get_lunchmoney_app()
    return await fetch_budget_settings(client=client)
