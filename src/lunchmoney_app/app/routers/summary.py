"""Budget summary endpoints."""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import SummaryResponseObject

from lunchmoney_app.app.dependencies import OperationContext, get_operation_context
from lunchmoney_app.services import fetch_account_summary

router = APIRouter(tags=["Summary"])


@router.get(
    path="/summary",
    response_model=SummaryResponseObject,
    operation_id="get_account_summary",
)
async def get_account_summary(
    start_date: datetime.date,
    end_date: datetime.date,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
    include_exclude_from_budgets: bool | None = None,
    include_occurrences: bool | None = None,
    include_past_budget_dates: bool | None = None,
    include_totals: bool | None = None,
    include_rollover_pool: bool | None = None,
) -> SummaryResponseObject:
    """Return a budget summary for the requested date range."""
    return await fetch_account_summary(
        context,
        start_date,
        end_date,
        include_exclude_from_budgets,
        include_occurrences,
        include_past_budget_dates,
        include_totals,
        include_rollover_pool,
    )
