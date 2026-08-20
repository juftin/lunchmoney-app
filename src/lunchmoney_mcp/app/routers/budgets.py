"""Live budget settings endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
import datetime

from lunchmoney.models import (
    BudgetSettingsResponseObject,
    BudgetUpsertResponseObject,
    UpsertBudgetRequestObject,
)

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
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
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
) -> BudgetSettingsResponseObject:
    """Fetch the authenticated user's budget-period settings.

    **Parameters:**

    - **client**: Configured Lunch Money API client.

    **Returns:** Upstream budget-period settings.
    """
    return await fetch_budget_settings(db=db, client=client)


@router.put(
    path="/budgets",
    response_model=BudgetUpsertResponseObject,
    operation_id="upsert_budget",
)
async def upsert_budget(
    request: UpsertBudgetRequestObject,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> BudgetUpsertResponseObject:
    """Set one category's budget value for a budget period."""
    return await set_budget_value(client=client, db=db, request=request)


@router.delete(
    path="/budgets",
    status_code=204,
    operation_id="clear_budget",
)
async def clear_budget(
    category_id: int,
    start_date: datetime.date,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> None:
    """Clear one category's budget value for a budget period."""
    await clear_budget_value(
        client=client,
        db=db,
        category_id=category_id,
        start_date=start_date,
    )
