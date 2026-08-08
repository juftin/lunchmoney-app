"""Service logic for live Lunch Money recurring-item queries."""

import datetime

from lunchmoney.models import (
    RecurringObject,
    RecurringObjectMatches,
    RecurringObjectMatchesFoundTransactionsInner,
)

from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import RecurringItem, Transaction


async def fetch_recurring_items(
    db: LunchMoneyDatabase,
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
    del include_suggested
    transactions = await db.list(Transaction)
    items: list[RecurringObject] = []
    for item in await db.list(RecurringItem):
        recurring = RecurringObject.model_validate(item.payload)
        matches = [
            RecurringObjectMatchesFoundTransactionsInner.model_validate(
                {"var_date": transaction.var_date, "transaction_id": transaction.id}
            )
            for transaction in transactions
            if transaction.recurring_id == recurring.id
            and (start_date is None or transaction.var_date >= start_date)
            and (end_date is None or transaction.var_date <= end_date)
        ]
        items.append(
            recurring.model_copy(
                update={
                    "matches": RecurringObjectMatches(
                        request_start_date=start_date,
                        request_end_date=end_date,
                        found_transactions=matches,
                    )
                }
            )
        )
    return items


async def fetch_recurring_item_by_id(
    db: LunchMoneyDatabase,
    recurring_item_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> RecurringObject | None:
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
    items = await fetch_recurring_items(db=db, start_date=start_date, end_date=end_date)
    return next((item for item in items if item.id == recurring_item_id), None)
