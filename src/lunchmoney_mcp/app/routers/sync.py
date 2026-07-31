"""Synchronization API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import ScheduledSyncStatus, SyncResponse
from lunchmoney_mcp.services import execute_sync, get_scheduled_sync_status

router = APIRouter(tags=["Sync"])
"""FastAPI APIRouter for synchronization endpoints."""


@router.post(
    path="/sync",
    response_model=SyncResponse,
    operation_id="sync_database",
)
async def sync(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    days: int = 30,
    incremental: bool = False,
    safety_margin_minutes: int | None = None,
) -> SyncResponse:
    """Initialize the schema and synchronize Lunch Money data for a date window.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    client : LunchMoneyApp
        Lunch Money API client wrapper.
    days : int
        Number of past calendar days to pull transactions for. Default is 30.
    incremental : bool
        Whether to resume transaction sync from its successful watermark.
    safety_margin_minutes : int | None
        Optional overlap override for an incremental transaction sync.

    Returns
    -------
    SyncResponse
        Status summary and record counts of synchronized objects.
    """
    return await execute_sync(
        db=db,
        client=client,
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
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> ScheduledSyncStatus | None:
    """Return the final result of the most recent scheduled synchronization."""
    return await get_scheduled_sync_status(db=db)
