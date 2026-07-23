"""Tests for async database configuration and lifecycle."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import lunchmoney_mcp.database as database_package
from lunchmoney_mcp.database import DEFAULT_DATABASE_URL, LunchMoneyDatabase
from lunchmoney_mcp.database.backend import resolve_database_url


def test_database_package_exports_documented_public_api() -> None:
    """Expose every database symbol used by the public documentation."""
    documented_symbols = {
        "Category",
        "CategoryKind",
        "DEFAULT_DATABASE_URL",
        "LunchMoneyDatabase",
        "ManualAccount",
        "PlaidAccount",
        "Tag",
        "Transaction",
        "TransactionAttachment",
        "TransactionKind",
        "TransactionTagLink",
        "User",
        "resolve_database_url",
    }

    assert documented_symbols <= set(database_package.__all__)
    assert all(
        getattr(database_package, symbol, None) is not None
        for symbol in documented_symbols
    )


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


def test_database_uses_environment_url_without_explicit_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the configured environment URL when construction has no URL."""
    database_url = "sqlite+aiosqlite:///environment.db"
    monkeypatch.setenv("LUNCHMONEY_DATABASE_URL", database_url)

    database = LunchMoneyDatabase()

    assert str(database.engine.url) == database_url


@pytest.mark.asyncio
async def test_database_exposes_native_async_session(tmp_path: Path) -> None:
    """Yield SQLModel's native async session and dispose cleanly."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'database.db'}"
    async with LunchMoneyDatabase(url) as database:
        assert isinstance(database.engine, AsyncEngine)
        async with database.session() as session:
            assert isinstance(session, AsyncSession)


@pytest.mark.asyncio
async def test_documented_sqlite_example_uses_public_api(
    migrated_database_url: str,
) -> None:
    """Run the documented SQLite workflow without external services."""
    user = database_package.User(
        id=1,
        name="Synthetic User",
        email="synthetic-user@example.invalid",
        account_id=100,
        budget_name="Synthetic Budget",
        primary_currency="usd",
        api_key_label="Synthetic key",
    )

    async with database_package.LunchMoneyDatabase(migrated_database_url) as database:
        await database.upsert(user)

        async with database.session() as session:
            result = await session.exec(
                select(database_package.User).where(
                    database_package.User.account_id == 100
                )
            )
            assert result.one().email == "synthetic-user@example.invalid"

        assert await database.get(database_package.User, 1) is not None
        assert len(await database.list(database_package.User)) == 1
        assert await database.delete(database_package.User, 1) is True
