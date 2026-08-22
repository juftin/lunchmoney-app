"""Service logic for live Lunch Money budget settings queries."""

import datetime

from lunchmoney.models import (
    BudgetSettingsResponseObject,
    BudgetUpsertResponseObject,
    UpsertBudgetRequestObject,
)

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase


async def fetch_budget_settings(
    db: LunchMoneyDatabase,
    client: LunchMoneyApp,
) -> BudgetSettingsResponseObject:
    """Fetch the authenticated user's budget-period settings.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database containing synchronized budget-settings snapshots.
    client : LunchMoneyApp
        Configured Lunch Money API client used to populate an absent snapshot.

    Returns
    -------
    BudgetSettingsResponseObject
        Upstream budget-period settings.
    """
    payload = await db.get_cached_response("budget-settings")
    if payload is not None:
        return BudgetSettingsResponseObject.model_validate(payload)
    settings = await client.client.budgets.get_budget_settings()
    await db.upsert_cached_response("budget-settings", settings.model_dump(mode="json"))
    return settings


async def set_budget_value(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    request: UpsertBudgetRequestObject,
) -> BudgetUpsertResponseObject:
    """Set a category's budget value for one budget period upstream.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    db : LunchMoneyDatabase
        Database whose affected summary snapshots must be invalidated.
    request : UpsertBudgetRequestObject
        Validated category, period, amount, and optional currency or notes.

    Returns
    -------
    BudgetUpsertResponseObject
        Canonical budget value returned by Lunch Money.
    """
    response = await client.client.budgets.upsert_budget(
        upsert_budget_request_object=request,
    )
    await db.delete_cached_responses("summary:")
    return response


async def clear_budget_value(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    category_id: int,
    start_date: datetime.date,
) -> None:
    """Clear a category's budget value for one budget period upstream.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    db : LunchMoneyDatabase
        Database whose affected summary snapshots must be invalidated.
    category_id : int
        Identifier of the budget category to clear.
    start_date : datetime.date
        Start date of the budget period to clear.
    """
    await client.client.budgets.delete_budget(
        category_id=category_id,
        start_date=start_date,
    )
    await db.delete_cached_responses("summary:")
