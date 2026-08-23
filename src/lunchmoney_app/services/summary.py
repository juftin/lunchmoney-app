"""Service logic for budget-summary operations."""

import datetime

from lunchmoney.models import SummaryResponseObject

from lunchmoney_app.services.adapters.summary import SummaryQuery
from lunchmoney_app.services.operations import OperationContext


async def fetch_account_summary(
    context: OperationContext,
    start_date: datetime.date,
    end_date: datetime.date,
    include_exclude_from_budgets: bool | None = None,
    include_occurrences: bool | None = None,
    include_past_budget_dates: bool | None = None,
    include_totals: bool | None = None,
    include_rollover_pool: bool | None = None,
) -> SummaryResponseObject:
    """Return a shaped summary through the selected reader."""
    return await context.summary.get(
        SummaryQuery(
            start_date=start_date,
            end_date=end_date,
            include_exclude_from_budgets=include_exclude_from_budgets,
            include_occurrences=include_occurrences,
            include_past_budget_dates=include_past_budget_dates,
            include_totals=include_totals,
            include_rollover_pool=include_rollover_pool,
        )
    )
