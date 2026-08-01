"""Live recurring-item endpoints."""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import RecurringObject

from lunchmoney_mcp.app.dependencies import get_lunchmoney_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.services import fetch_recurring_item_by_id, fetch_recurring_items

router = APIRouter(tags=["Recurring Items"])
"""FastAPI APIRouter for live recurring-item endpoints."""


@router.get(
    path="/recurring_items",
    response_model=list[RecurringObject],
    operation_id="list_recurring_items",
)
async def list_recurring_items(
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    include_suggested: bool | None = None,
) -> list[RecurringObject]:
    """List live recurring items with optional matching information.

    **Parameters:**

    - **client**: Configured Lunch Money API client.
    - **start_date**: Optional matching window start date.
    - **end_date**: Optional matching window end date.
    - **include_suggested**: Whether suggested recurring items should be returned.

    **Returns:** Recurring items returned by Lunch Money.
    """
    return await fetch_recurring_items(
        client=client,
        start_date=start_date,
        end_date=end_date,
        include_suggested=include_suggested,
    )


@router.get(
    path="/recurring_items/{recurring_item_id}",
    response_model=RecurringObject,
    operation_id="get_recurring_item",
)
async def get_recurring_item(
    recurring_item_id: int,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> RecurringObject:
    """Fetch one live recurring item with optional matching information.

    **Parameters:**

    - **recurring_item_id**: Identifier of the recurring item to retrieve.
    - **client**: Configured Lunch Money API client.
    - **start_date**: Optional matching window start date.
    - **end_date**: Optional matching window end date.

    **Returns:** Recurring item returned by Lunch Money.
    """
    return await fetch_recurring_item_by_id(
        client=client,
        recurring_item_id=recurring_item_id,
        start_date=start_date,
        end_date=end_date,
    )
