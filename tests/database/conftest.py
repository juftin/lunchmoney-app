"""Shared fixtures for asynchronous persistence integration tests."""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config

from lunchmoney_app.database import LunchMoneyDatabase

PROJECT_ROOT = Path(__file__).parents[2]
"""Repository root containing the Alembic migration environment."""


@pytest.fixture
def migrated_database_url(tmp_path: Path) -> Iterator[str]:
    """Apply and reverse real migrations around one persistent SQLite file."""
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'persistence.db'}"
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location", str(PROJECT_ROOT / "src/lunchmoney_app/database/migrations")
    )
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")
    yield database_url
    command.downgrade(config, "base")


@pytest.fixture
def migrated_postgres_database_url() -> Iterator[str]:
    """Apply and always reverse migrations around the optional PostgreSQL test."""
    database_url = os.getenv("TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("TEST_POSTGRES_URL is not configured")
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location", str(PROJECT_ROOT / "src/lunchmoney_app/database/migrations")
    )
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        yield database_url
    finally:
        command.downgrade(config, "base")


@pytest_asyncio.fixture
async def database(
    migrated_database_url: str,
) -> AsyncIterator[LunchMoneyDatabase]:
    """Provide an initialized persistent SQLite database for one test."""
    async with LunchMoneyDatabase(migrated_database_url) as test_database:
        yield test_database
