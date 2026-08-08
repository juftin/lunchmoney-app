"""Service logic for live Lunch Money budget settings queries."""

import datetime

from lunchmoney.models import (
    BudgetSettingsResponseObject,
    BudgetUpsertResponseObject,
    UpsertBudgetRequestObject,
)

from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase


async def fetch_budget_settings(
    db: LunchMoneyDatabase,
) -> BudgetSettingsResponseObject | None:
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
    payload = await db.get_cached_response("budget-settings")
    return BudgetSettingsResponseObject.model_validate(payload) if payload else None


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
    return await client.client.budgets.upsert_budget(
        upsert_budget_request_object=request,
    )


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
