"""Liveness, readiness, and protected metrics endpoints."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.config import get_settings
from lunchmoney_mcp.observability import log_event, metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])
"""Operational endpoints which avoid exposing financial data."""


async def database_is_ready() -> bool:
    """Return whether the configured database can accept a minimal query."""
    try:
        database = get_database()
        async with database.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        log_event(logger, "database_readiness_failed")
        return False
    return True


def scheduler_status(
    request: Request,
) -> Literal["ready", "not_configured", "unavailable"]:
    """Return embedded scheduler readiness without starting or probing another process."""
    if not get_settings().embed_scheduler:
        return "not_configured"
    scheduler = getattr(request.app.state, "scheduler", None)
    return "ready" if scheduler is not None and scheduler.running else "unavailable"


@router.get(path="/health", include_in_schema=False)
@router.get(path="/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Confirm the ASGI process is live without testing its dependencies."""
    return {"status": "ok"}


@router.get(path="/ready", include_in_schema=False)
@router.get(path="/readyz", include_in_schema=False)
async def readyz(request: Request) -> JSONResponse:
    """Report whether database and configured embedded scheduler are ready."""
    database_status = "ready" if await database_is_ready() else "unavailable"
    current_scheduler_status = scheduler_status(request)
    scheduler_ready = current_scheduler_status != "unavailable"
    is_ready = database_status == "ready" and scheduler_ready
    content = {
        "status": "ready" if is_ready else "not_ready",
        "database": database_status,
        "scheduler": current_scheduler_status,
    }
    return JSONResponse(status_code=200 if is_ready else 503, content=content)


@router.get(path="/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Expose bounded operational metrics after API-key middleware authorization."""
    return Response(
        content=metrics.render(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


__all__ = ["database_is_ready", "router", "scheduler_status"]
