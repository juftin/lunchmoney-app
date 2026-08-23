"""Budget endpoints."""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import (
    BudgetSettingsResponseObject,
    BudgetUpsertResponseObject,
    UpsertBudgetRequestObject,
)

from lunchmoney_app.app.dependencies import OperationContext, get_operation_context
from lunchmoney_app.services import (
    clear_budget_value,
    fetch_budget_settings,
    set_budget_value,
)

router = APIRouter(tags=["Budgets"])


@router.get(
    path="/budgets/settings",
    response_model=BudgetSettingsResponseObject,
    operation_id="get_budget_settings",
)
async def get_budget_settings(
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> BudgetSettingsResponseObject:
    """Return the authenticated user's budget-period settings."""
    return await fetch_budget_settings(context)


@router.put(
    path="/budgets",
    response_model=BudgetUpsertResponseObject,
    operation_id="upsert_budget",
)
async def upsert_budget(
    request: UpsertBudgetRequestObject,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> BudgetUpsertResponseObject:
    """Set one category's budget value for a period."""
    return await set_budget_value(context, request)


@router.delete(path="/budgets", status_code=204, operation_id="clear_budget")
async def clear_budget(
    category_id: int,
    start_date: datetime.date,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> None:
    """Clear one category's budget value for a period."""
    await clear_budget_value(context, category_id, start_date)
