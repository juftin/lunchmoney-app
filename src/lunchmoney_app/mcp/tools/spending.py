"""FastMCP spending analytics tools."""

import datetime
from typing import Literal

from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.schemas import GroupedSpendingResponse, SpendingTrendsResponse
from lunchmoney_app.services import fetch_category_spending, fetch_spending_trends
from lunchmoney_app.services.operations import get_operation_context


@mcp.tool()
async def get_category_spending(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    days: int | None = 30,
) -> GroupedSpendingResponse:
    """Return grouped spending over an inclusive period."""
    return await fetch_category_spending(
        get_operation_context(), start_date, end_date, days
    )


@mcp.tool()
async def get_spending_trends(
    granularity: Literal["daily", "weekly", "monthly"] = "monthly",
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    days: int | None = 30,
) -> SpendingTrendsResponse:
    """Return calendar-bucketed spending and income trends."""
    return await fetch_spending_trends(
        get_operation_context(), granularity, start_date, end_date, days
    )


__all__ = ["get_category_spending", "get_spending_trends"]
