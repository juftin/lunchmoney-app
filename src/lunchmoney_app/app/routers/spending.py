"""Spending analytics endpoints."""

import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from lunchmoney_app.app.dependencies import OperationContext, get_operation_context
from lunchmoney_app.schemas import GroupedSpendingResponse, SpendingTrendsResponse
from lunchmoney_app.services import fetch_category_spending, fetch_spending_trends

router = APIRouter(tags=["Spending"])


@router.get(
    path="/spending/category",
    response_model=GroupedSpendingResponse,
    operation_id="get_category_spending",
)
async def get_category_spending(
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    days: int | None = 30,
) -> GroupedSpendingResponse:
    """Return grouped category spending for an inclusive period."""
    return await fetch_category_spending(context, start_date, end_date, days)


@router.get(
    path="/spending/trends",
    response_model=SpendingTrendsResponse,
    operation_id="get_spending_trends",
)
async def get_spending_trends(
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
    granularity: Literal["daily", "weekly", "monthly"] = "monthly",
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    days: int | None = 30,
) -> SpendingTrendsResponse:
    """Return calendar-bucketed spending and income trends."""
    return await fetch_spending_trends(context, granularity, start_date, end_date, days)
