"""
FastAPI application lifespan management.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lunchmoney_app.app.dependencies import get_shared_database
from lunchmoney_app.config import (
    get_secret_settings,
    get_settings,
    validate_persistence_configuration,
)
from lunchmoney_app.database import run_migrations
from lunchmoney_app.locks import LockTimeoutError, get_migration_lock
from lunchmoney_app.scheduler import start_embedded_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize storage and optionally a local embedded scheduler for FastAPI."""
    settings = get_settings()
    validate_persistence_configuration(settings, get_secret_settings())
    if settings.persistence_mode == "ephemeral":
        logger.info("Starting database-free ephemeral runtime")
        yield
        return

    db = get_shared_database()
    if db.database_url.startswith("sqlite") and (
        ":memory:" in db.database_url or "mode=memory" in db.database_url
    ):
        logger.info("Initializing explicitly configured in-memory SQLite schema...")
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
    if settings.embed_scheduler:
        scheduler = start_embedded_scheduler()
        app.state.scheduler = scheduler

    try:
        yield
    finally:
        if scheduler is not None:
            await stop_scheduler(scheduler)
        if get_shared_database.cache_info().currsize > 0:
            await db.dispose()
            get_shared_database.cache_clear()


__all__ = ["lifespan"]
