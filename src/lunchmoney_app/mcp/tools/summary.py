"""FastMCP tools for live Lunch Money budget summary queries."""

import datetime
from typing import TYPE_CHECKING

from lunchmoney.models import SummaryResponseObject

from lunchmoney_app.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.services import fetch_account_summary

if TYPE_CHECKING:
    pass


@mcp.tool()
async def get_account_summary(
    start_date: datetime.date,
    end_date: datetime.date,
    include_exclude_from_budgets: bool | None = None,
    include_occurrences: bool | None = None,
    include_past_budget_dates: bool | None = None,
    include_totals: bool | None = None,
    include_rollover_pool: bool | None = None,
) -> SummaryResponseObject | None:
    """Fetch a live budget summary for the requested date range.

    Parameters
    ----------
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
        Whether top-level totals should be included.
    include_rollover_pool : bool | None
        Whether rollover-pool details should be included.

    Returns
    -------
    SummaryResponseObject
        Upstream budget summary response for the requested range.
    """
    return await fetch_account_summary(
        db=get_database(),
        client=get_lunchmoney_app(),
        start_date=start_date,
        end_date=end_date,
        include_exclude_from_budgets=include_exclude_from_budgets,
        include_occurrences=include_occurrences,
        include_past_budget_dates=include_past_budget_dates,
        include_totals=include_totals,
        include_rollover_pool=include_rollover_pool,
    )
