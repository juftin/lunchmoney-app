"""Service logic for Lunch Money database synchronization."""

import asyncio
import contextlib
import datetime
import logging
import time
from typing import Literal, cast

from lunchmoney.exceptions import ApiException

from lunchmoney_app.app.sync import SyncScope, sync_database
from lunchmoney_app.client import LunchMoneyApp, SyncSummary
from lunchmoney_app.database import LunchMoneyDatabase, ScheduledSyncRun, run_migrations
from lunchmoney_app.locks import (
    Lock,
    LockOwnershipLostError,
    LockTimeoutError,
    get_migration_lock,
)
from lunchmoney_app.observability import metrics
from lunchmoney_app.schemas import (
    ScheduledSyncStatus,
    SyncDetails,
    SyncResponse,
    SyncResult,
)
from lunchmoney_app.services.operations import clear_unpersisted_stale_domains

logger = logging.getLogger(__name__)


def _validate_sync_parameters(*, days: int, safety_margin_minutes: int | None) -> None:
    """Reject date-window values that could silently skip upstream data."""
    if days < 1:
        msg = "days must be greater than or equal to 1"
        raise ValueError(msg)
    if safety_margin_minutes is not None and safety_margin_minutes < 0:
        msg = "safety_margin_minutes must be greater than or equal to 0"
        raise ValueError(msg)


async def execute_sync(
    db: LunchMoneyDatabase,
    client: LunchMoneyApp,
    days: int = 30,
    incremental: bool = False,
    safety_margin_minutes: int | None = None,
    scope: SyncScope = SyncScope.ALL,
    *,
    _lock_blocking: bool = True,
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
    scope : SyncScope
        Domain workload to synchronize. Interactive calls default to all domains.
    _lock_blocking : bool
        Whether this caller waits for the shared migration/synchronization lock.
        Scheduled jobs use nonblocking acquisition so contention is recorded as a
        skipped run.

    Returns
    -------
    SyncResponse
        Status summary and record counts of synchronized objects.
    """
    _validate_sync_parameters(days=days, safety_margin_minutes=safety_margin_minutes)
    started_at = time.perf_counter()
    lock = get_migration_lock(timeout=-1 if _lock_blocking else 0)
    if not await _acquire_lock(lock=lock, blocking=_lock_blocking):
        raise LockTimeoutError("Another migration or synchronization is running")
    renewal_task: asyncio.Task[None] | None = None
    ownership_lost = asyncio.Event()
    if lock.renewal_interval is not None:
        owner_task = asyncio.current_task()
        if owner_task is None:  # pragma: no cover - asyncio always owns this coroutine
            msg = "Synchronization must run inside an asyncio task"
            raise RuntimeError(msg)
        renewal_task = asyncio.create_task(
            _renew_lock_while_held(
                lock=lock, owner_task=owner_task, ownership_lost=ownership_lost
            ),
            name="lunchmoney-sync-lock-renewal",
        )
    try:
        if db.database_url.startswith("sqlite") and (
            ":memory:" in db.database_url or "mode=memory" in db.database_url
        ):
            logger.info(
                "Initializing in-memory schema and triggering %s-day sync...", days
            )
            await db.create_tables()
        else:
            logger.info("Triggering database migrations and %s-day sync...", days)
            await run_migrations(database_url=db.database_url)
        summary: SyncSummary = await sync_database(
            db=db,
            client=client,
            days=days,
            incremental=incremental,
            safety_margin_minutes=safety_margin_minutes,
            scope=scope,
        )
        try:
            await db.delete_cached_responses("health:stale:")
        except Exception:
            logger.exception("Unable to clear cache projection health markers")
        else:
            clear_unpersisted_stale_domains()
    except asyncio.CancelledError as error:
        if not ownership_lost.is_set():
            raise
        metrics.record_sync(
            status="failure", duration_seconds=time.perf_counter() - started_at
        )
        raise LockOwnershipLostError(
            "Synchronization stopped after losing distributed lock ownership"
        ) from error
    except Exception as error:
        metrics.record_sync(
            status="failure", duration_seconds=time.perf_counter() - started_at
        )
        if isinstance(error, ApiException):
            metrics.record_upstream_failure(error)
        raise
    finally:
        if renewal_task is not None:
            renewal_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await renewal_task
        try:
            await asyncio.to_thread(lock.release)
        except Exception:
            if not ownership_lost.is_set():
                raise
            logger.exception(
                "Unable to release synchronization lock after ownership loss"
            )
    metrics.record_sync(
        status="success", duration_seconds=time.perf_counter() - started_at
    )
    metrics.record_cache_refresh()
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


async def _acquire_lock(*, lock: Lock, blocking: bool) -> bool:
    """Acquire without blocking the event loop or leaking a cancelled acquisition."""
    while True:
        acquire_task = asyncio.create_task(
            asyncio.to_thread(lock.acquire, blocking, 0.25 if blocking else 0),
            name="lunchmoney-sync-lock-acquisition",
        )
        try:
            acquired = await asyncio.shield(acquire_task)
        except asyncio.CancelledError:
            acquired = await acquire_task
            if acquired:
                await asyncio.to_thread(lock.release)
            raise
        if acquired or not blocking:
            return acquired


async def _renew_lock_while_held(
    *,
    lock: Lock,
    owner_task: asyncio.Task[object],
    ownership_lost: asyncio.Event,
) -> None:
    """Keep a lease alive and stop work immediately if ownership is lost."""
    interval = lock.renewal_interval
    if interval is None:
        return
    while True:
        await asyncio.sleep(interval)
        try:
            renewed = await asyncio.to_thread(lock.renew)
        except Exception:
            logger.exception("Unable to renew synchronization lock ownership")
            renewed = False
        if not renewed:
            logger.error("Lost synchronization lock ownership during renewal")
            ownership_lost.set()
            owner_task.cancel("Synchronization lock ownership was lost")
            return


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
    scope: SyncScope = SyncScope.ALL,
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
    scope : SyncScope
        Metadata or transaction workload selected by the triggering schedule.

    Returns
    -------
    ScheduledSyncStatus
        Final successful, failed, or skipped run status.
    """
    started_at = datetime.datetime.now(datetime.timezone.utc)
    try:
        incremental = True
        if scope in {SyncScope.ALL, SyncScope.TRANSACTIONS}:
            authoritative = await db.get_sync_metadata("transactions:authoritative")
            incremental = authoritative is not None and (
                started_at - authoritative.last_synced_at < datetime.timedelta(days=1)
            )
        response = await execute_sync(
            db=db,
            client=client,
            days=days,
            incremental=incremental,
            scope=scope,
            _lock_blocking=False,
        )
    except LockTimeoutError:
        result = ScheduledSyncStatus(
            status="skipped",
            started_at=started_at,
            finished_at=datetime.datetime.now(datetime.timezone.utc),
            message="Skipped because another migration or synchronization is running.",
        )
    except Exception:
        logger.exception("Scheduled synchronization failed")
        result = ScheduledSyncStatus(
            status="failed",
            started_at=started_at,
            finished_at=datetime.datetime.now(datetime.timezone.utc),
            message="Scheduled synchronization failed; inspect server logs for details.",
        )
    else:
        result = ScheduledSyncStatus(
            status="success",
            started_at=started_at,
            finished_at=datetime.datetime.now(datetime.timezone.utc),
            synced=response.synced,
        )
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
