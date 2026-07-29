"""Tests for application configuration and Pydantic Settings."""

from pathlib import Path

import pytest

from lunchmoney_mcp.config import (
    DEFAULT_DATABASE_URL,
    IN_MEMORY_DATABASE_URL,
    Settings,
    get_settings,
)
from lunchmoney_mcp.database import resolve_database_url


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve default settings when environment variables are omitted.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest environment monkeypatching fixture.
    """
    monkeypatch.delenv("LUNCHMONEY_DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("LUNCHMONEY_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("STATELESS", raising=False)
    monkeypatch.delenv("LUNCHMONEY_SYNC_SAFETY_MARGIN_MINUTES", raising=False)

    settings = Settings()
    assert settings.lunchmoney_database_url == DEFAULT_DATABASE_URL
    assert settings.redis_url is None
    assert settings.lunchmoney_access_token is None
    assert settings.stateless is False
    assert settings.sync_safety_margin_minutes == 5


def test_settings_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override settings values via environment variables.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest environment monkeypatching fixture.
    """
    monkeypatch.setenv(
        "LUNCHMONEY_DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db"
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("STATELESS", "true")
    monkeypatch.setenv("LUNCHMONEY_SYNC_SAFETY_MARGIN_MINUTES", "10")

    settings = Settings()
    assert (
        settings.lunchmoney_database_url
        == "postgresql+asyncpg://user:pass@localhost/db"
    )
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.lunchmoney_access_token == "test-token"
    assert settings.stateless is True
    assert settings.sync_safety_margin_minutes == 10


def test_stateless_settings_select_shared_memory_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve the shared in-memory URL when stateless mode is enabled."""
    monkeypatch.setenv("STATELESS", "true")
    monkeypatch.delenv("LUNCHMONEY_DATABASE_URL", raising=False)
    get_settings.cache_clear()

    assert resolve_database_url() == IN_MEMORY_DATABASE_URL
    get_settings.cache_clear()


def test_database_url_overrides_stateless_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve explicit and environment database URL precedence in stateless mode."""
    environment_url = "sqlite+aiosqlite:///environment.db"
    explicit_url = "sqlite+aiosqlite:///explicit.db"
    monkeypatch.setenv("STATELESS", "true")
    monkeypatch.setenv("LUNCHMONEY_DATABASE_URL", environment_url)
    get_settings.cache_clear()

    assert resolve_database_url() == environment_url
    assert resolve_database_url(explicit_url) == explicit_url
    get_settings.cache_clear()


def test_dotenv_database_url_overrides_stateless_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Preserve a database URL supplied through Pydantic's `.env` source."""
    dotenv_url = "sqlite+aiosqlite:///dotenv.db"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STATELESS", "true")
    monkeypatch.delenv("LUNCHMONEY_DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text(f"LUNCHMONEY_DATABASE_URL={dotenv_url}\n")
    get_settings.cache_clear()

    assert resolve_database_url() == dotenv_url
    get_settings.cache_clear()


def test_get_settings_cached() -> None:
    """Return a cached Settings instance."""
    settings_1 = get_settings()
    settings_2 = get_settings()
    assert settings_1 is settings_2
