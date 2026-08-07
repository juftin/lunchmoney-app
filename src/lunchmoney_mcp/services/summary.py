"""Service logic for live Lunch Money budget summary queries."""

import datetime

from lunchmoney.models import SummaryResponseObject

from lunchmoney_mcp.client import LunchMoneyApp


async def fetch_account_summary(
    client: LunchMoneyApp,
    start_date: datetime.date,
    end_date: datetime.date,
    include_exclude_from_budgets: bool | None = None,
    include_occurrences: bool | None = None,
    include_past_budget_dates: bool | None = None,
    include_totals: bool | None = None,
    include_rollover_pool: bool | None = None,
    force_refresh: bool = False,
) -> SummaryResponseObject:
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
    force_refresh : bool
        Whether to bypass client cache and force an upstream API call.

    Returns
    -------
    SummaryResponseObject
        Upstream budget summary response for the requested range.
    """
    from lunchmoney_mcp.client import LunchableData

    cache_key = (
        start_date,
        end_date,
        include_exclude_from_budgets,
        include_occurrences,
        include_past_budget_dates,
        include_totals,
        include_rollover_pool,
    )
    data = getattr(client, "data", None)
    if (
        not force_refresh
        and isinstance(data, LunchableData)
        and cache_key in data.summaries
    ):
        return data.summaries[cache_key]

    res = await client.client.summary.get_budget_summary(
        start_date=start_date,
        end_date=end_date,
        include_exclude_from_budgets=include_exclude_from_budgets,
        include_occurrences=include_occurrences,
        include_past_budget_dates=include_past_budget_dates,
        include_totals=include_totals,
        include_rollover_pool=include_rollover_pool,
    )
    if isinstance(data, LunchableData):
        data.summaries[cache_key] = res
    return res
