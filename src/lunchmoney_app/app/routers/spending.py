"""Spending breakdown API endpoints."""

import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from lunchmoney_app.app.dependencies import get_database
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.schemas import GroupedSpendingResponse, SpendingTrendsResponse
from lunchmoney_app.services import fetch_category_spending, fetch_spending_trends

router = APIRouter(tags=["Spending"])
"""FastAPI APIRouter for grouped spending analysis endpoints."""


@router.get(
    path="/spending/category",
    response_model=GroupedSpendingResponse,
    operation_id="get_category_spending",
)
async def get_category_spending(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    days: int | None = 30,
) -> GroupedSpendingResponse:
    """Fetch grouped spending analysis by category over specified date range.

    **Parameters:**

    - **db**: Database manager instance.
    - **start_date**: Optional start date for transaction filtering.
    - **end_date**: Optional end date for transaction filtering.
    - **days**: Number of past days to query when `start_date` is omitted. Defaults to 30.

    **Returns:** Grouped spending report with parent/child category rollups and totals.
    """
    return await fetch_category_spending(
        db=db, start_date=start_date, end_date=end_date, days=days
    )


@router.get(
    path="/spending/trends",
    response_model=SpendingTrendsResponse,
    operation_id="get_spending_trends",
)
async def get_spending_trends(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    granularity: Literal["daily", "weekly", "monthly"] = "monthly",
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    days: int | None = 30,
) -> SpendingTrendsResponse:
    """Fetch time-series income and spending totals over a date range."""
    return await fetch_spending_trends(
        db=db,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        days=days,
    )
