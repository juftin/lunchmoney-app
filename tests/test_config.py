"""Tests for application configuration and Pydantic Settings."""

import pytest

from lunchmoney_mcp.config import DEFAULT_DATABASE_URL, Settings, get_settings


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

    settings = Settings()
    assert settings.lunchmoney_database_url == DEFAULT_DATABASE_URL
    assert settings.redis_url is None
    assert settings.lunchmoney_access_token is None


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

    settings = Settings()
    assert (
        settings.lunchmoney_database_url
        == "postgresql+asyncpg://user:pass@localhost/db"
    )
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.lunchmoney_access_token == "test-token"


def test_get_settings_cached() -> None:
    """Return a cached Settings instance."""
    settings_1 = get_settings()
    settings_2 = get_settings()
    assert settings_1 is settings_2
