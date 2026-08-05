"""Service logic for live Lunch Money recurring-item queries."""

import datetime

from lunchmoney.models import RecurringObject

from lunchmoney_mcp.client import LunchMoneyApp


async def fetch_recurring_items(
    client: LunchMoneyApp,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    include_suggested: bool | None = None,
) -> list[RecurringObject]:
    """Fetch recurring items and optional transaction matching details.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    start_date : datetime.date | None
        Optional matching window start date.
    end_date : datetime.date | None
        Optional matching window end date.
    include_suggested : bool | None
        Whether suggested recurring items should be returned.

    Returns
    -------
    list[RecurringObject]
        Recurring items returned by Lunch Money for the requested window.
    """
    response = await client.client.recurring_items.get_all_recurring(
        start_date=start_date,
        end_date=end_date,
        include_suggested=include_suggested,
    )
    return response.recurring_items or []


async def fetch_recurring_item_by_id(
    client: LunchMoneyApp,
    recurring_item_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> RecurringObject:
    """Fetch one recurring item and its optional matching details.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    recurring_item_id : int
        Identifier of the recurring item to retrieve.
    start_date : datetime.date | None
        Optional matching window start date.
    end_date : datetime.date | None
        Optional matching window end date.

    Returns
    -------
    RecurringObject
        Upstream recurring item matching the supplied identifier.
    """
    return await client.client.recurring_items.get_recurring_by_id(
        id=recurring_item_id,
        start_date=start_date,
        end_date=end_date,
    )
