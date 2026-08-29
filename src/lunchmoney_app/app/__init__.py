"""Lunch Money MCP application package."""

import sys

if sys.platform == "emscripten":
    __all__: list[str] = []
else:
    from lunchmoney_app.app.dependencies import (
        get_database,
        get_db_session,
        get_lunchmoney_app,
    )
    from lunchmoney_app.app.lifespan import lifespan
    from lunchmoney_app.app.main import app, fastapi_app, mcp, mcp_app
    from lunchmoney_app.app.sync import sync_database
    from lunchmoney_app.database import run_migrations

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
