"""FastMCP tools for live Lunch Money recurring-item queries."""

import datetime
from typing import TYPE_CHECKING

from lunchmoney.models import RecurringObject

from lunchmoney_mcp.app.dependencies import get_lunchmoney_app
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.services import fetch_recurring_item_by_id, fetch_recurring_items

if TYPE_CHECKING:
    from lunchmoney_mcp.client import LunchMoneyApp


@mcp.tool()
async def list_recurring_items(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    include_suggested: bool | None = None,
) -> list[RecurringObject]:
    """List live recurring items with optional matching information.

    Parameters
    ----------
    start_date : datetime.date | None
        Optional matching window start date.
    end_date : datetime.date | None
        Optional matching window end date.
    include_suggested : bool | None
        Whether suggested recurring items should be returned.

    Returns
    -------
    list[RecurringObject]
        Recurring items returned by Lunch Money.
    """
    client: LunchMoneyApp = get_lunchmoney_app()
    return await fetch_recurring_items(
        client=client,
        start_date=start_date,
        end_date=end_date,
        include_suggested=include_suggested,
    )


@mcp.tool()
async def get_recurring_item(
    recurring_item_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> RecurringObject:
    """Fetch one live recurring item with optional matching information.

    Parameters
    ----------
    recurring_item_id : int
        Identifier of the recurring item to retrieve.
    start_date : datetime.date | None
        Optional matching window start date.
    end_date : datetime.date | None
        Optional matching window end date.

    Returns
    -------
    RecurringObject
        Recurring item returned by Lunch Money.
    """
    client: LunchMoneyApp = get_lunchmoney_app()
    return await fetch_recurring_item_by_id(
        client=client,
        recurring_item_id=recurring_item_id,
        start_date=start_date,
        end_date=end_date,
    )
