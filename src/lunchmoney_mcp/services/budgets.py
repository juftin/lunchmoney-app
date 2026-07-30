"""Service logic for live Lunch Money budget settings queries."""

from lunchmoney.models import BudgetSettingsResponseObject

from lunchmoney_mcp.client import LunchMoneyApp


async def fetch_budget_settings(
    client: LunchMoneyApp,
) -> BudgetSettingsResponseObject:
    """Fetch the authenticated user's budget-period settings.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.

    Returns
    -------
    BudgetSettingsResponseObject
        Upstream budget-period settings.
    """
    return await client.client.budgets.get_budget_settings()
