"""
FastAPI dependencies for Lunch Money MCP.
"""

from collections.abc import AsyncIterator
from functools import cache
from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase


@cache
def get_database() -> LunchMoneyDatabase:
    """FastAPI dependency supplying the shared LunchMoneyDatabase instance."""
    return LunchMoneyDatabase()


async def get_db_session(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped AsyncSession."""
    async with db.session() as session:
        yield session


def get_lunchmoney_app() -> LunchMoneyApp:
    """FastAPI dependency supplying a LunchMoneyApp client instance."""
    return LunchMoneyApp(cache=False)


__all__ = ["get_database", "get_db_session", "get_lunchmoney_app"]
