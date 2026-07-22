"""Async SQLModel database configuration and lifecycle helpers."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

DEFAULT_DATABASE_URL: str = "sqlite+aiosqlite:///lunchmoney.db"
"""Persistent SQLite database URL used when no URL is configured."""


def resolve_database_url(database_url: str | None = None) -> str:
    """Resolve an explicit, environment-provided, or default database URL."""
    if database_url is not None:
        return database_url
    return os.getenv("LUNCHMONEY_DATABASE_URL", DEFAULT_DATABASE_URL)


class LunchMoneyDatabase:
    """Own the application's async database engine and session factory."""

    engine: AsyncEngine
    """Engine used for all database connections."""
    session_factory: async_sessionmaker[AsyncSession]
    """Factory that creates native SQLModel asynchronous sessions."""

    def __init__(self, database_url: str | None = None) -> None:
        """Create database resources for the resolved connection URL."""
        self.engine = create_async_engine(resolve_database_url(database_url))
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session and close it without committing caller operations."""
        async with self.session_factory() as session:
            yield session

    async def __aenter__(self) -> Self:
        """Return this database instance for async context manager use."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Dispose engine resources when leaving an async context manager."""
        await self.dispose()

    async def dispose(self) -> None:
        """Release all connections held by the underlying async engine."""
        await self.engine.dispose()
