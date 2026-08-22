"""Live budget summary endpoints."""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import SummaryResponseObject

from lunchmoney_app.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.services import fetch_account_summary

router = APIRouter(tags=["Summary"])
"""FastAPI APIRouter for live budget summary endpoints."""


@router.get(
    path="/summary",
    response_model=SummaryResponseObject,
    operation_id="get_account_summary",
)
async def get_account_summary(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    start_date: datetime.date,
    end_date: datetime.date,
    include_exclude_from_budgets: bool | None = None,
    include_occurrences: bool | None = None,
    include_past_budget_dates: bool | None = None,
    include_totals: bool | None = None,
    include_rollover_pool: bool | None = None,
) -> SummaryResponseObject:
    """Fetch a live budget summary for the requested date range.

    **Parameters:**

    - **client**: Configured Lunch Money API client.
    - **start_date**: Inclusive start of the requested budget range.
    - **end_date**: Inclusive end of the requested budget range.
    - **include_exclude_from_budgets**: Whether excluded categories should be included.
    - **include_occurrences**: Whether category budget occurrences should be included.
    - **include_past_budget_dates**: Whether prior occurrences should be included with occurrences.
    - **include_totals**: Whether top-level totals should be included.
    - **include_rollover_pool**: Whether rollover-pool details should be included.

    **Returns:** Upstream budget summary response for the requested range.
    """
    return await fetch_account_summary(
        db=db,
        client=client,
        start_date=start_date,
        end_date=end_date,
        include_exclude_from_budgets=include_exclude_from_budgets,
        include_occurrences=include_occurrences,
        include_past_budget_dates=include_past_budget_dates,
        include_totals=include_totals,
        include_rollover_pool=include_rollover_pool,
    )
