"""Service logic for recurring-item operations."""

import datetime

from lunchmoney.models import RecurringObject

from lunchmoney_app.services.adapters.recurring import RecurringQuery
from lunchmoney_app.services.operations import OperationContext


async def fetch_recurring_items(
    context: OperationContext,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    include_suggested: bool | None = None,
) -> list[RecurringObject]:
    """Return recurring items through the selected reader."""
    return await context.recurring.list(
        RecurringQuery(
            start_date=start_date,
            end_date=end_date,
            include_suggested=include_suggested,
        )
    )


async def fetch_recurring_item_by_id(
    context: OperationContext,
    recurring_item_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> RecurringObject:
    """Return one recurring item through the selected reader."""
    return await context.recurring.get(recurring_item_id, start_date, end_date)
