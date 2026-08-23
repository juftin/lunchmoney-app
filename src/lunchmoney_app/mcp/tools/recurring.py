"""FastMCP recurring-item tools."""

import datetime

from lunchmoney.models import RecurringObject

from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.services import fetch_recurring_item_by_id, fetch_recurring_items
from lunchmoney_app.services.operations import get_operation_context


@mcp.tool()
async def list_recurring_items(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    include_suggested: bool | None = None,
) -> list[RecurringObject]:
    """List recurring items with optional matching information."""
    return await fetch_recurring_items(
        get_operation_context(), start_date, end_date, include_suggested
    )


@mcp.tool()
async def get_recurring_item(
    recurring_item_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> RecurringObject:
    """Return one recurring item."""
    return await fetch_recurring_item_by_id(
        get_operation_context(), recurring_item_id, start_date, end_date
    )


__all__ = ["get_recurring_item", "list_recurring_items"]
