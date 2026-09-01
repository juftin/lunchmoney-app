"""Recurring-item endpoints."""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import RecurringObject

from lunchmoney_app.app.dependencies import OperationContext, get_operation_context
from lunchmoney_app.services import fetch_recurring_item_by_id, fetch_recurring_items

router = APIRouter(tags=["Recurring Items"])


@router.get(
    path="/recurring_items",
    response_model=list[RecurringObject],
    operation_id="list_recurring_items",
)
async def list_recurring_items(
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    include_suggested: bool | None = None,
) -> list[RecurringObject]:
    """List recurring items with optional matching information."""
    return await fetch_recurring_items(context, start_date, end_date, include_suggested)


@router.get(
    path="/recurring_items/{recurring_item_id}",
    response_model=RecurringObject,
    operation_id="get_recurring_item",
)
async def get_recurring_item(
    recurring_item_id: int,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> RecurringObject:
    """Return one recurring item with optional matching information."""
    return await fetch_recurring_item_by_id(
        context, recurring_item_id, start_date, end_date
    )
