"""Database lifecycles shared by REST and MCP service entrypoints."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from uuid import uuid4

from lunchmoney_mcp.app.sync import sync_database
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.config import get_settings
from lunchmoney_mcp.database import LunchMoneyDatabase

_operation_database: ContextVar[LunchMoneyDatabase | None] = ContextVar(
    "operation_database", default=None
)


def get_operation_database() -> LunchMoneyDatabase | None:
    """Return the database bound to the current request or MCP call."""
    return _operation_database.get()


@asynccontextmanager
async def data_operation(
    client: LunchMoneyApp,
    database: LunchMoneyDatabase | None,
    days: int = 30,
    refresh: bool = True,
) -> AsyncIterator[LunchMoneyDatabase]:
    """Yield the database appropriate to one service operation.

    Ephemeral operations receive a private, fully refreshed in-memory database
    which is disposed unconditionally when the operation completes.
    """
    settings = get_settings()
    if not settings.ephemeral:
        if database is None:
            msg = "A shared database is required outside ephemeral mode"
            raise RuntimeError(msg)
        token: Token[LunchMoneyDatabase | None] = _operation_database.set(database)
        try:
            if settings.stateless and refresh:
                await database.create_tables()
                await sync_database(db=database, client=client, days=days)
            yield database
        finally:
            _operation_database.reset(token)
        return

    url = f"sqlite+aiosqlite:///file:operation-{uuid4().hex}?mode=memory&cache=shared&uri=true"
    ephemeral_database = LunchMoneyDatabase(database_url=url)
    token = _operation_database.set(ephemeral_database)
    try:
        await ephemeral_database.create_tables()
        if refresh:
            await sync_database(db=ephemeral_database, client=client, days=days)
        yield ephemeral_database
    finally:
        _operation_database.reset(token)
        await ephemeral_database.dispose()
