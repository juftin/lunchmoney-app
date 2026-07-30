"""Live budget settings endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
import datetime

from lunchmoney.models import (
    BudgetSettingsResponseObject,
    BudgetUpsertResponseObject,
    UpsertBudgetRequestObject,
)

from lunchmoney_mcp.app.dependencies import get_lunchmoney_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.services import (
    clear_budget_value,
    fetch_budget_settings,
    set_budget_value,
)

router = APIRouter(tags=["Budgets"])
"""FastAPI APIRouter for live budget settings endpoints."""


@router.get(
    path="/budgets/settings",
    response_model=BudgetSettingsResponseObject,
    operation_id="get_budget_settings",
)
async def get_budget_settings(
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
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
    return await fetch_budget_settings(client=client)


@router.put(
    path="/budgets",
    response_model=BudgetUpsertResponseObject,
    operation_id="upsert_budget",
)
async def upsert_budget(
    request: UpsertBudgetRequestObject,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
) -> BudgetUpsertResponseObject:
    """Set one category's budget value for a budget period."""
    return await set_budget_value(client=client, request=request)


@router.delete(
    path="/budgets",
    status_code=204,
    operation_id="clear_budget",
)
async def clear_budget(
    category_id: int,
    start_date: datetime.date,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
) -> None:
    """Clear one category's budget value for a budget period."""
    await clear_budget_value(
        client=client,
        category_id=category_id,
        start_date=start_date,
    )
