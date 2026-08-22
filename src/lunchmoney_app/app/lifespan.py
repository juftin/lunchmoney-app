"""
FastAPI application lifespan management.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lunchmoney_app.app.dependencies import get_shared_database
from lunchmoney_app.config import get_settings
from lunchmoney_app.database import run_migrations
from lunchmoney_app.locks import LockTimeoutError, get_migration_lock
from lunchmoney_app.scheduler import start_embedded_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize storage and optionally a local embedded scheduler for FastAPI."""
    if get_settings().ephemeral:
        db = None
    else:
        db = get_shared_database()
    if db is None:
        logger.info("Deferring ephemeral database setup to each operation...")
    elif db.is_stateless:
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
        if get_shared_database.cache_info().currsize > 0:
            db = get_shared_database()
            await db.dispose()
            get_shared_database.cache_clear()


__all__ = ["lifespan"]
