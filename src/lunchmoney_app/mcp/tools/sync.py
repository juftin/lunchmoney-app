"""FastMCP tools for database synchronization operations."""

from typing import Annotated

from pydantic import Field

from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.schemas import ScheduledSyncStatus, SyncResult
from lunchmoney_app.services import execute_mcp_sync, get_scheduled_sync_status

from lunchmoney_app.services.operations import get_stateful_operation_context


@mcp.tool()
async def sync_data(
    days: Annotated[int, Field(ge=1)] = 30,
    incremental: bool = False,
    safety_margin_minutes: Annotated[int | None, Field(ge=0)] = None,
) -> SyncResult:
    """Synchronize transactions, accounts, categories, and tags from Lunch Money API.

    Parameters
    ----------
    days : int
        Number of days back from today to synchronize. Default is 30.
    incremental : bool
        Whether to resume transaction sync from its successful watermark.
    safety_margin_minutes : int | None
        Optional overlap override for an incremental transaction sync.

    Returns
    -------
    SyncResult
        Summary of synchronized records.
    """
    context = get_stateful_operation_context()
    return await execute_mcp_sync(
        db=context.database,
        client=context.client,
        days=days,
        incremental=incremental,
        safety_margin_minutes=safety_margin_minutes,
    )


@mcp.tool()
async def get_sync_status() -> ScheduledSyncStatus | None:
    """Return the result of the latest attempted scheduled synchronization."""
    return await get_scheduled_sync_status(db=get_stateful_operation_context().database)


__all__ = ["get_sync_status", "sync_data"]
