"""Service logic for budget operations."""

import datetime

from lunchmoney.models import (
    BudgetSettingsResponseObject,
    BudgetUpsertResponseObject,
    UpsertBudgetRequestObject,
)

from lunchmoney_app.services.operations import OperationContext


async def fetch_budget_settings(
    context: OperationContext,
) -> BudgetSettingsResponseObject:
    """Return budget settings through the selected reader."""
    return await context.budgets.get_settings()


async def set_budget_value(
    context: OperationContext,
    request: UpsertBudgetRequestObject,
) -> BudgetUpsertResponseObject:
    """Set a budget upstream, then invalidate derived state."""
    response = await context.client.client.budgets.upsert_budget(
        upsert_budget_request_object=request
    )
    await context.project("budgets", context.budgets.invalidate())
    return response


async def clear_budget_value(
    context: OperationContext,
    category_id: int,
    start_date: datetime.date,
) -> None:
    """Clear a budget upstream, then invalidate derived state."""
    await context.client.client.budgets.delete_budget(
        category_id=category_id, start_date=start_date
    )
    await context.project("budgets", context.budgets.invalidate())
