"""Lunch Money MCP application package."""

from lunchmoney_mcp.app.app import app, fastapi_app, mcp, mcp_app
from lunchmoney_mcp.app.dependencies import (
    get_database,
    get_db_session,
    get_lunchmoney_app,
)
from lunchmoney_mcp.app.lifespan import lifespan
from lunchmoney_mcp.app.sync import sync_database
from lunchmoney_mcp.database import run_migrations

__all__ = [
    "app",
    "fastapi_app",
    "get_database",
    "get_db_session",
    "get_lunchmoney_app",
    "lifespan",
    "mcp",
    "mcp_app",
    "run_migrations",
    "sync_database",
]
