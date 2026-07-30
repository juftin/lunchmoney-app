"""Live budget settings endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import BudgetSettingsResponseObject

from lunchmoney_mcp.app.dependencies import get_lunchmoney_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.services import fetch_budget_settings

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
