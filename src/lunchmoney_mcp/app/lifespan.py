"""
FastAPI application lifespan management.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase, run_migrations
from lunchmoney_mcp.locks import LockTimeoutError, get_migration_lock

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize the configured database schema for the application lifespan."""
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

    yield
    if get_database.cache_info().currsize > 0:
        db = get_database()
        await db.dispose()
        get_database.cache_clear()


__all__ = ["lifespan"]
