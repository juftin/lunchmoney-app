"""Service logic for live Lunch Money recurring-item queries."""

import datetime

from lunchmoney.models import RecurringObject

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import RecurringItem


async def fetch_recurring_items(
    db: LunchMoneyDatabase,
    client: LunchMoneyApp,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    include_suggested: bool | None = None,
) -> list[RecurringObject]:
    """Fetch recurring items and optional transaction matching details.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database containing synchronized recurring response snapshots.
    client : LunchMoneyApp
        Configured Lunch Money API client used to populate an absent snapshot.
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
        response = await client.client.recurring_items.get_all_recurring(
            start_date=start_date,
            end_date=end_date,
            include_suggested=True,
        )
        payload = {
            "items": [
                item.model_dump(mode="json") for item in response.recurring_items or []
            ]
        }
        await db.upsert_cached_response(cache_key, payload)
    items = [RecurringObject.model_validate(item) for item in payload["items"]]
    if include_suggested is True:
        return items
    return [item for item in items if item.status != "suggested"]


async def fetch_recurring_item_by_id(
    db: LunchMoneyDatabase,
    client: LunchMoneyApp,
    recurring_item_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> RecurringObject:
    """Fetch one recurring item and its optional matching details.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database containing synchronized recurring response snapshots.
    client : LunchMoneyApp
        Configured Lunch Money API client used to populate an absent snapshot.
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
    if start_date is None and end_date is None:
        cached_item = await db.get(RecurringItem, recurring_item_id)
        if cached_item is not None:
            return RecurringObject.model_validate(cached_item.payload)

    item = await client.client.recurring_items.get_recurring_by_id(
        id=recurring_item_id,
        start_date=start_date,
        end_date=end_date,
    )
    if start_date is None and end_date is None:
        await db.upsert(RecurringItem(id=item.id, payload=item.model_dump(mode="json")))
    return item
