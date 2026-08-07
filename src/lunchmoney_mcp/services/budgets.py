"""Service logic for live Lunch Money budget settings queries."""

import datetime

from lunchmoney.models import (
    BudgetSettingsResponseObject,
    BudgetUpsertResponseObject,
    UpsertBudgetRequestObject,
)

from lunchmoney_mcp.client import LunchableData, LunchMoneyApp


async def fetch_budget_settings(
    client: LunchMoneyApp,
    force_refresh: bool = False,
) -> BudgetSettingsResponseObject:
    """Fetch the authenticated user's budget-period settings.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    force_refresh : bool
        Whether to bypass client cache and force an upstream API call.

    Returns
    -------
    BudgetSettingsResponseObject
        Upstream budget-period settings.
    """
    data = getattr(client, "data", None)
    if (
        not force_refresh
        and isinstance(data, LunchableData)
        and data.budget_settings is not None
    ):
        return data.budget_settings

    res = await client.client.budgets.get_budget_settings()
    if isinstance(data, LunchableData):
        data.budget_settings = res
    return res


async def set_budget_value(
    client: LunchMoneyApp,
    request: UpsertBudgetRequestObject,
) -> BudgetUpsertResponseObject:
    """Set a category's budget value for one budget period upstream.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    request : UpsertBudgetRequestObject
        Validated category, period, amount, and optional currency or notes.

    Returns
    -------
    BudgetUpsertResponseObject
        Canonical budget value returned by Lunch Money.
    """
    res = await client.client.budgets.upsert_budget(
        upsert_budget_request_object=request,
    )
    data = getattr(client, "data", None)
    if isinstance(data, LunchableData):
        data.summaries.clear()
    return res


async def clear_budget_value(
    client: LunchMoneyApp,
    category_id: int,
    start_date: datetime.date,
) -> None:
    """Clear a category's budget value for one budget period upstream.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    category_id : int
        Identifier of the budget category to clear.
    start_date : datetime.date
        Start date of the budget period to clear.
    """
    await client.client.budgets.delete_budget(
        category_id=category_id,
        start_date=start_date,
    )
    data = getattr(client, "data", None)
    if isinstance(data, LunchableData):
        data.summaries.clear()
