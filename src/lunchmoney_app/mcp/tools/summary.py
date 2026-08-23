"""FastMCP summary tools."""

import datetime

from lunchmoney.models import SummaryResponseObject

from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.services import fetch_account_summary
from lunchmoney_app.services.operations import get_operation_context


@mcp.tool()
async def get_account_summary(
    start_date: datetime.date,
    end_date: datetime.date,
    include_exclude_from_budgets: bool | None = None,
    include_occurrences: bool | None = None,
    include_past_budget_dates: bool | None = None,
    include_totals: bool | None = None,
    include_rollover_pool: bool | None = None,
) -> SummaryResponseObject:
    """Return a budget summary for the requested period."""
    return await fetch_account_summary(
        get_operation_context(),
        start_date,
        end_date,
        include_exclude_from_budgets,
        include_occurrences,
        include_past_budget_dates,
        include_totals,
        include_rollover_pool,
    )


__all__ = ["get_account_summary"]
