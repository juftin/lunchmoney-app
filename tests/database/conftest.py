"""Shared fixtures for asynchronous persistence integration tests."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from sqlmodel import SQLModel

from lunchmoney_mcp.database import LunchMoneyDatabase


@pytest_asyncio.fixture
async def database(tmp_path: Path) -> AsyncIterator[LunchMoneyDatabase]:
    """Provide an initialized persistent SQLite database for one test."""
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'persistence.db'}"
    async with LunchMoneyDatabase(database_url) as test_database:
        async with test_database.engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        yield test_database
        async with test_database.engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.drop_all)
