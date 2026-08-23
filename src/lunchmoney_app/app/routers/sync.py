"""Synchronization API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_app.schemas import ScheduledSyncStatus, SyncResponse
from lunchmoney_app.services import execute_sync, get_scheduled_sync_status
from lunchmoney_app.services.operations import (
    StatefulOperationContext,
    get_stateful_operation_context,
)

router = APIRouter(tags=["Sync"])
"""FastAPI APIRouter for synchronization endpoints."""


@router.post(
    path="/sync",
    response_model=SyncResponse,
    operation_id="sync_database",
)
async def sync(
    context: Annotated[
        StatefulOperationContext, Depends(dependency=get_stateful_operation_context)
    ],
    days: int = 30,
    incremental: bool = False,
    safety_margin_minutes: int | None = None,
) -> SyncResponse:
    """Initialize the schema and synchronize Lunch Money data for a date window.

    **Parameters:**

    - **db**: Database manager instance.
    - **client**: Lunch Money API client wrapper.
    - **days**: Number of past calendar days to pull transactions for. Defaults to 30.
    - **incremental**: Whether to resume transaction sync from its successful watermark.
    - **safety_margin_minutes**: Optional overlap override for an incremental transaction sync.

    **Returns:** Status summary and record counts of synchronized objects.
    """
    return await execute_sync(
        db=context.database,
        client=context.client,
        days=days,
        incremental=incremental,
        safety_margin_minutes=safety_margin_minutes,
    )


@router.get(
    path="/sync/status",
    response_model=ScheduledSyncStatus | None,
    operation_id="get_scheduled_sync_status",
)
async def scheduled_sync_status(
    context: Annotated[
        StatefulOperationContext, Depends(dependency=get_stateful_operation_context)
    ],
) -> ScheduledSyncStatus | None:
    """Return the final result of the most recent scheduled synchronization."""
    return await get_scheduled_sync_status(db=context.database)
