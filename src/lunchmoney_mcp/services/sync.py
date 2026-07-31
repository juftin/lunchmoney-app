"""Service logic for Lunch Money database synchronization."""

import datetime
import logging
from typing import Literal, cast

from lunchmoney_mcp.app.sync import sync_database
from lunchmoney_mcp.client import LunchMoneyApp, SyncSummary
from lunchmoney_mcp.database import LunchMoneyDatabase, ScheduledSyncRun, run_migrations
from lunchmoney_mcp.locks import get_migration_lock
from lunchmoney_mcp.schemas import (
    ScheduledSyncStatus,
    SyncDetails,
    SyncResponse,
    SyncResult,
)

logger = logging.getLogger(__name__)


async def execute_sync(
    db: LunchMoneyDatabase,
    client: LunchMoneyApp,
    days: int = 30,
    incremental: bool = False,
    safety_margin_minutes: int | None = None,
) -> SyncResponse:
    """Initialize the database schema and synchronize Lunch Money data.

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
    if db.is_stateless:
        logger.info("Initializing stateless schema and triggering %s-day sync...", days)
        await db.create_tables()
    else:
        logger.info("Triggering database migrations and %s-day sync...", days)
        await run_migrations()
    summary: SyncSummary = await sync_database(
        db=db,
        client=client,
        days=days,
        incremental=incremental,
        safety_margin_minutes=safety_margin_minutes,
    )
    details = SyncDetails(
        user=summary.user,
        plaid_accounts=summary.plaid_accounts,
        manual_accounts=summary.manual_accounts,
        categories=summary.categories,
        tags=summary.tags,
        transactions=summary.transactions,
        total=summary.total,
    )
    return SyncResponse(message="Synchronization complete", synced=details)


async def execute_mcp_sync(
    db: LunchMoneyDatabase,
    client: LunchMoneyApp,
    days: int = 30,
    incremental: bool = False,
    safety_margin_minutes: int | None = None,
) -> SyncResult:
    """Execute sync for MCP tool returning SyncResult schema.

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
    SyncResult
        MCP tool result format.
    """
    response = await execute_sync(
        db=db,
        client=client,
        days=days,
        incremental=incremental,
        safety_margin_minutes=safety_margin_minutes,
    )
    return SyncResult(status="success", synced_records=response.synced)


async def run_scheduled_sync(
    db: LunchMoneyDatabase,
    client: LunchMoneyApp,
    days: int = 30,
) -> ScheduledSyncStatus:
    """Run the scheduled metadata and incremental transaction synchronization.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager used for the synchronization and its persisted result.
    client : LunchMoneyApp
        Lunch Money API client wrapper.
    days : int
        Rolling transaction window used when no transaction watermark exists.

    Returns
    -------
    ScheduledSyncStatus
        Final successful, failed, or skipped run status.
    """
    started_at = datetime.datetime.now(datetime.UTC)
    lock = get_migration_lock()
    if not lock.acquire(blocking=False):
        result = ScheduledSyncStatus(
            status="skipped",
            started_at=started_at,
            finished_at=datetime.datetime.now(datetime.UTC),
            message="Skipped because another migration or synchronization is running.",
        )
        await _record_scheduled_sync_status(db=db, status=result)
        return result

    try:
        response = await execute_sync(
            db=db,
            client=client,
            days=days,
            incremental=True,
        )
    except Exception:
        logger.exception("Scheduled synchronization failed")
        result = ScheduledSyncStatus(
            status="failed",
            started_at=started_at,
            finished_at=datetime.datetime.now(datetime.UTC),
            message="Scheduled synchronization failed; inspect server logs for details.",
        )
    else:
        result = ScheduledSyncStatus(
            status="success",
            started_at=started_at,
            finished_at=datetime.datetime.now(datetime.UTC),
            synced=response.synced,
        )
    finally:
        lock.release()

    await _record_scheduled_sync_status(db=db, status=result)
    return result


async def get_scheduled_sync_status(
    db: LunchMoneyDatabase,
) -> ScheduledSyncStatus | None:
    """Return the latest persisted scheduled synchronization result.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager containing scheduler run records.

    Returns
    -------
    ScheduledSyncStatus | None
        Latest scheduler run result, or None before the first run.
    """
    run = await db.get_latest_scheduled_sync_run()
    if run is None:
        return None
    status = cast(Literal["success", "failed", "skipped"], run.status)
    synced = SyncDetails.model_validate(run.synced) if run.synced is not None else None
    return ScheduledSyncStatus(
        status=status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        message=run.message,
        synced=synced,
    )


async def _record_scheduled_sync_status(
    db: LunchMoneyDatabase,
    status: ScheduledSyncStatus,
) -> None:
    """Persist a scheduler result without hiding its original successful outcome."""
    try:
        await db.record_scheduled_sync_run(
            ScheduledSyncRun(
                status=status.status,
                started_at=status.started_at,
                finished_at=status.finished_at,
                message=status.message,
                synced=(
                    status.synced.model_dump(mode="json")
                    if status.synced is not None
                    else None
                ),
            )
        )
    except Exception:
        logger.exception("Unable to record scheduled synchronization status")
