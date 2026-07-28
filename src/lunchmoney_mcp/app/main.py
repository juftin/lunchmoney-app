"""FastAPI application for Lunch Money MCP."""

import logging

from fastapi import FastAPI
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.utilities.lifespan import combine_lifespans

from lunchmoney_mcp.app.lifespan import lifespan
from lunchmoney_mcp.app.routers import (
    accounts_router,
    categories_router,
    sync_router,
    transactions_router,
    user_router,
)
from lunchmoney_mcp.mcp import mcp
from lunchmoney_mcp.schemas import RootResponse

logger: logging.Logger = logging.getLogger(__name__)

fastapi_app = FastAPI(
    title="Lunch Money MCP",
    description="Lunch Money Model Context Protocol Server & API",
    lifespan=lifespan,
)


@fastapi_app.get(
    path="/",
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


fastapi_app.include_router(sync_router)
fastapi_app.include_router(user_router)
fastapi_app.include_router(categories_router)
fastapi_app.include_router(accounts_router)
fastapi_app.include_router(transactions_router)

mcp_app: StarletteWithLifespan = mcp.http_app(path="/mcp")
app = FastAPI(
    routes=[
        *mcp_app.routes,
        *fastapi_app.routes,
    ],
    lifespan=combine_lifespans(mcp_app.lifespan, lifespan),
)

__all__: list[str] = [
    "app",
    "fastapi_app",
    "mcp",
    "mcp_app",
]

if __name__ == "__main__":
    mcp.run()
