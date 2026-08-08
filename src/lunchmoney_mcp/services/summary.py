"""Service logic for live Lunch Money budget summary queries."""

import datetime

from lunchmoney.models import SummaryResponseObject

from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Category


async def fetch_account_summary(
    db: LunchMoneyDatabase,
    start_date: datetime.date,
    end_date: datetime.date,
    include_exclude_from_budgets: bool | None = None,
    include_occurrences: bool | None = None,
    include_past_budget_dates: bool | None = None,
    include_totals: bool | None = None,
    include_rollover_pool: bool | None = None,
) -> SummaryResponseObject | None:
    """Fetch a live budget summary for a specified date range.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    start_date : datetime.date
        Inclusive start of the requested budget range.
    end_date : datetime.date
        Inclusive end of the requested budget range.
    include_exclude_from_budgets : bool | None
        Whether excluded categories should be included.
    include_occurrences : bool | None
        Whether category budget occurrences should be included.
    include_past_budget_dates : bool | None
        Whether prior occurrences should be included with occurrences.
    include_totals : bool | None
        Whether top-level inflow and outflow totals should be included.
    include_rollover_pool : bool | None
        Whether rollover-pool details should be included.

    Returns
    -------
    SummaryResponseObject
        Upstream budget summary response for the requested range.
    """
    payload = await db.get_cached_response(f"summary:{start_date}:{end_date}")
    if payload is None:
        return None
    summary = SummaryResponseObject.model_validate(payload)
    categories = {category.id: category for category in await db.list(Category)}
    rows = summary.categories
    if include_exclude_from_budgets is not True:
        rows = [
            row
            for row in rows
            if (category := categories.get(row.category_id)) is None
            or not category.exclude_from_budget
        ]
    if include_occurrences is not True:
        rows = [row.model_copy(update={"occurrences": None}) for row in rows]
    elif include_past_budget_dates is not True:
        rows = [
            row.model_copy(
                update={
                    "occurrences": [
                        occurrence
                        for occurrence in row.occurrences or []
                        if occurrence.in_range
                    ]
                }
            )
            for row in rows
        ]
    return summary.model_copy(
        update={
            "categories": rows,
            "totals": summary.totals if include_totals else None,
            "rollover_pool": summary.rollover_pool if include_rollover_pool else None,
        }
    )
