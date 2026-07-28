"""
FastAPI application for Lunch Money MCP.
"""

import logging

from fastapi import FastAPI
from fastmcp import FastMCP

from lunchmoney_mcp.app.dependencies import (
    get_database,
    get_db_session,
    get_lunchmoney_app,
)
from lunchmoney_mcp.app.lifespan import lifespan
from lunchmoney_mcp.app.routers import (
    accounts_router,
    categories_router,
    sync_router,
    transactions_router,
    user_router,
)
from lunchmoney_mcp.app.sync import sync_database
from lunchmoney_mcp.database import run_migrations
from lunchmoney_mcp.schemas import RootResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Lunch Money MCP",
    description="Lunch Money Model Context Protocol Server & API",
    lifespan=lifespan,
)


@app.get(path="/", response_model=RootResponse, tags=["Health"])
async def root() -> RootResponse:
    """Root endpoint returning status message."""
    return RootResponse(message="Hello World")


app.include_router(sync_router)
app.include_router(user_router)
app.include_router(categories_router)
app.include_router(accounts_router)
app.include_router(transactions_router)

mcp: FastMCP[None] = FastMCP.from_fastapi(app=app)
fastapi_app = app

__all__: list[str] = [
    "app",
    "fastapi_app",
    "get_database",
    "get_db_session",
    "get_lunchmoney_app",
    "lifespan",
    "mcp",
    "run_migrations",
    "sync_database",
]

if __name__ == "__main__":
    mcp.run()
