"""Service logic for live Lunch Money recurring-item queries."""

import datetime

from lunchmoney.models import RecurringObject

from lunchmoney_mcp.database import LunchMoneyDatabase


async def fetch_recurring_items(
    db: LunchMoneyDatabase,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    include_suggested: bool | None = None,
) -> list[RecurringObject]:
    """Fetch recurring items and optional transaction matching details.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database containing synchronized recurring response snapshots.
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
    cache_key = (
        f"recurring:{start_date}:{end_date}"
        if start_date is not None or end_date is not None
        else "recurring:latest"
    )
    payload = await db.get_cached_response(cache_key)
    if payload is None:
        return []
    items = [RecurringObject.model_validate(item) for item in payload["items"]]
    if include_suggested is True:
        return items
    return [item for item in items if item.status != "suggested"]


async def fetch_recurring_item_by_id(
    db: LunchMoneyDatabase,
    recurring_item_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> RecurringObject | None:
    """Fetch one recurring item and its optional matching details.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database containing synchronized recurring response snapshots.
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
    items = await fetch_recurring_items(db=db, start_date=start_date, end_date=end_date)
    return next((item for item in items if item.id == recurring_item_id), None)
