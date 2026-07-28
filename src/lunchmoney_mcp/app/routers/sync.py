"""Synchronization API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import SyncResponse
from lunchmoney_mcp.services import execute_sync

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
) -> SyncResponse:
    """Run database migrations and synchronize Lunch Money data for specified date window.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    client : LunchMoneyApp
        Lunch Money API client wrapper.
    days : int
        Number of past calendar days to pull transactions for. Default is 30.

    Returns
    -------
    SyncResponse
        Status summary and record counts of synchronized objects.
    """
    return await execute_sync(db=db, client=client, days=days)
