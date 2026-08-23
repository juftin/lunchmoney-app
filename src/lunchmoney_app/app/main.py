"""FastAPI application for Lunch Money MCP."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.utilities.lifespan import combine_lifespans

from lunchmoney_app.app.auth import verify_api_key
from lunchmoney_app.app.dependencies import get_lunchmoney_app, get_shared_database
from lunchmoney_app.app.lifespan import lifespan
from lunchmoney_app.app.routers import (
    accounts_router,
    budgets_router,
    categories_router,
    dashboard_router,
    health_router,
    recurring_router,
    spending_router,
    summary_router,
    sync_router,
    tags_router,
    transactions_router,
    user_router,
)
from lunchmoney_app.app.security import apply_security_middleware
from lunchmoney_app.config import get_settings
from lunchmoney_app.logging_config import apply_logging_config
from lunchmoney_app.mcp import mcp
from lunchmoney_app.observability import log_event, metrics
from lunchmoney_app.schemas import RootResponse
from lunchmoney_app.services.operations import (
    EphemeralOperationContextFactory,
    OperationContext,
    OperationContextFactory,
    StatefulOperationContextFactory,
)
from lunchmoney_app.services.errors import StatefulModeRequired

apply_logging_config()

logger: logging.Logger = logging.getLogger(__name__)

fastapi_app = FastAPI(
    title="Lunch Money MCP",
    description="Lunch Money Model Context Protocol Server & API",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
api_router = APIRouter(prefix="/api")
"""Router namespace for every public REST API operation."""

fastapi_app.middleware("http")(verify_api_key)
fastapi_app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="dashboard_static",
)


async def bind_data_operation(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Bind one persistence-mode database lifecycle to a complete request."""
    operational_paths = {"/api", "/health", "/healthz", "/ready", "/readyz", "/metrics"}
    if request.url.path in operational_paths or request.url.path.startswith("/mcp"):
        return await call_next(request)
    normalized_path = request.url.path.rstrip("/") or "/"
    if get_settings().persistence_mode == "ephemeral" and normalized_path in {
        "/",
        "/dashboard/sync",
        "/api/sync",
        "/api/sync/status",
    }:
        raise StatefulModeRequired
    async with _operation_factory().operation():
        return await call_next(request)


def _operation_factory() -> OperationContextFactory[OperationContext]:
    """Select the concrete REST operation factory without optional storage."""
    client = get_lunchmoney_app()
    if get_settings().persistence_mode == "ephemeral":
        return EphemeralOperationContextFactory(client)
    return StatefulOperationContextFactory(client, get_shared_database())


fastapi_app.middleware("http")(bind_data_operation)


async def observe_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach a request ID and record safe request-level telemetry."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except StatefulModeRequired as error:
        status_code = 409
        response = JSONResponse(
            status_code=status_code,
            content={"detail": error.as_dict()},
        )
    except Exception:
        logger.exception(
            "Unhandled request failure path=%s request_id=%s",
            request.url.path,
            request_id,
        )
        response = JSONResponse(
            status_code=status_code,
            content={"detail": "Internal server error"},
        )
    response.headers["X-Request-ID"] = request_id
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    _record_request(
        request=request,
        request_id=request_id,
        status_code=status_code,
        duration_seconds=time.perf_counter() - started_at,
    )
    return response


def _record_request(
    request: Request,
    request_id: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """Record bounded metrics and a JSON log event for one completed request."""
    route = request.scope.get("route")
    path = getattr(route, "path", "unmatched")
    is_mcp = request.url.path.startswith("/mcp")
    metrics.record_http_request(
        method=request.method,
        path=path,
        status_code=status_code,
        duration_seconds=duration_seconds,
        is_mcp=is_mcp,
    )
    log_event(
        logger,
        "http_request",
        request_id=request_id,
        method=request.method,
        path=path,
        status_code=status_code,
        duration_ms=round(duration_seconds * 1000, 3),
    )


fastapi_app.middleware("http")(observe_request)


@fastapi_app.exception_handler(StatefulModeRequired)
async def stateful_mode_required_handler(
    request: Request,
    error: StatefulModeRequired,
) -> JSONResponse:
    """Map stateful-only operations to the stable REST conflict contract."""
    del request
    return JSONResponse(status_code=409, content={"detail": error.as_dict()})


@fastapi_app.get(
    path="/api",
    response_model=RootResponse,
    tags=["Health"],
    operation_id="get_root",
)
async def root() -> RootResponse:
    """Root endpoint returning status message.

    Returns
    -------
    RootResponse
        Health status message object.
    """
    return RootResponse(message="Hello World")


api_router.include_router(sync_router)
api_router.include_router(user_router)
api_router.include_router(summary_router)
api_router.include_router(budgets_router)
api_router.include_router(categories_router)
api_router.include_router(accounts_router)
api_router.include_router(transactions_router)
api_router.include_router(tags_router)
api_router.include_router(recurring_router)
api_router.include_router(spending_router)
fastapi_app.include_router(api_router)
fastapi_app.include_router(health_router)
fastapi_app.include_router(dashboard_router)

mcp_app: StarletteWithLifespan = mcp.http_app(path="/mcp")
app = FastAPI(
    title="Lunch Money MCP",
    description="Lunch Money Model Context Protocol Server & API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    routes=[
        *mcp_app.routes,
        *fastapi_app.routes,
    ],
    lifespan=combine_lifespans(mcp_app.lifespan, lifespan),
)

app.middleware("http")(verify_api_key)
app.middleware("http")(bind_data_operation)
app.middleware("http")(observe_request)
app.add_exception_handler(StatefulModeRequired, stateful_mode_required_handler)  # type: ignore[arg-type]
apply_security_middleware(app=app, settings=get_settings())

__all__: list[str] = [
    "app",
    "fastapi_app",
    "mcp",
    "mcp_app",
]

if __name__ == "__main__":
    mcp.run()
