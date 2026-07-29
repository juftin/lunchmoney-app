"""Spending breakdown API endpoints."""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import GroupedSpendingResponse
from lunchmoney_mcp.services import fetch_category_spending

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

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    start_date : datetime.date | None
        Optional start date for transaction filtering.
    end_date : datetime.date | None
        Optional end date for transaction filtering.
    days : int | None
        Number of past days to query if start_date is omitted. Default is 30.

    Returns
    -------
    GroupedSpendingResponse
        Grouped spending report with parent/child category rollups and totals.
    """
    return await fetch_category_spending(
        db=db, start_date=start_date, end_date=end_date, days=days
    )
