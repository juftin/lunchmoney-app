"""
FastAPI application lifespan management.
"""

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from filelock import FileLock, Timeout
from filelock._soft import SoftFileLock

from lunchmoney_mcp.database import LunchMoneyDatabase, run_migrations
from lunchmoney_mcp.dependencies import get_database

logger = logging.getLogger(__name__)


def _resolve_run_migrations() -> Any:
    """Resolve run_migrations function, respecting monkeypatches on lunchmoney_mcp.app."""
    app_module = sys.modules.get("lunchmoney_mcp.app")
    if app_module is not None and hasattr(app_module, "run_migrations"):
        return getattr(app_module, "run_migrations")
    return run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI application lifespan running single-worker database migrations."""
    lock: SoftFileLock = FileLock(lock_file=".lunchmoney_migration.lock", timeout=0)
    try:
        with lock:
            logger.info(
                "Worker acquired startup lock. Executing database migrations..."
            )
            fn = _resolve_run_migrations()
            await fn()
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
