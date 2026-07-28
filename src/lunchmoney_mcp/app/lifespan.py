"""
FastAPI application lifespan management.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from filelock import FileLock, Timeout
from filelock._soft import SoftFileLock

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase, run_migrations

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI application lifespan running single-worker database migrations."""
    lock: SoftFileLock = FileLock(lock_file=".lunchmoney_migration.lock", timeout=0)
    try:
        with lock:
            logger.info(
                "Worker acquired startup lock. Executing database migrations..."
            )
            await run_migrations()
    except Timeout:
        logger.debug(
            "Worker process skipped startup database migrations (lock held by another worker)."
        )

    yield
    if get_database.cache_info().currsize > 0:
        db: LunchMoneyDatabase = get_database()
        await db.dispose()
        get_database.cache_clear()


__all__ = ["lifespan"]
