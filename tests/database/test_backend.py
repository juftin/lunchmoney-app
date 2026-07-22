"""Tests for async database configuration and lifecycle."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from lunchmoney_mcp.database import DEFAULT_DATABASE_URL, LunchMoneyDatabase
from lunchmoney_mcp.database.backend import resolve_database_url


def test_default_database_url_is_persistent_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the persistent SQLite URL when no override exists."""
    monkeypatch.delenv("LUNCHMONEY_DATABASE_URL", raising=False)
    assert resolve_database_url() == DEFAULT_DATABASE_URL
    assert DEFAULT_DATABASE_URL == "sqlite+aiosqlite:///lunchmoney.db"


def test_explicit_database_url_precedes_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prefer an explicit database URL over the environment."""
    monkeypatch.setenv("LUNCHMONEY_DATABASE_URL", "sqlite+aiosqlite:///env.db")
    assert resolve_database_url("sqlite+aiosqlite:///explicit.db").endswith(
        "explicit.db"
    )


@pytest.mark.asyncio
async def test_database_exposes_native_async_session(tmp_path: Path) -> None:
    """Yield SQLModel's native async session and dispose cleanly."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'database.db'}"
    async with LunchMoneyDatabase(url) as database:
        assert isinstance(database.engine, AsyncEngine)
        async with database.session() as session:
            assert isinstance(session, AsyncSession)
