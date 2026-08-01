"""
FastAPI application lifespan management.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.config import get_settings
from lunchmoney_mcp.database import LunchMoneyDatabase, run_migrations
from lunchmoney_mcp.locks import LockTimeoutError, get_migration_lock
from lunchmoney_mcp.scheduler import start_embedded_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize storage and optionally a local embedded scheduler for FastAPI."""
    db: LunchMoneyDatabase = get_database()
    if db.is_stateless:
        logger.info("Initializing stateless in-memory database schema...")
        await db.create_tables()
    else:
        lock = get_migration_lock()
        try:
            with lock:
                logger.info(
                    "Worker acquired startup lock. Executing database migrations..."
                )
                await run_migrations()
        except LockTimeoutError:
            logger.debug(
                "Worker process skipped startup database migrations "
                "(lock held by another worker)."
            )

    scheduler = None
    if get_settings().embed_scheduler:
        scheduler = start_embedded_scheduler()
        app.state.scheduler = scheduler

    try:
        yield
    finally:
        if scheduler is not None:
            await stop_scheduler(scheduler)
        if get_database.cache_info().currsize > 0:
            db = get_database()
            await db.dispose()
            get_database.cache_clear()


__all__ = ["lifespan"]
