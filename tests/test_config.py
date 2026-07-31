"""Tests for application configuration and Pydantic Settings."""

import os
from pathlib import Path

import pytest

from lunchmoney_mcp.config import (
    DEFAULT_DATABASE_URL,
    IN_MEMORY_DATABASE_URL,
    Settings,
    configure_runtime_mode,
    export_runtime_settings,
    get_settings,
    parse_cli_settings,
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
    monkeypatch.delenv("LUNCHMONEY_MCP_API_KEY", raising=False)
    monkeypatch.delenv("LUNCHMONEY_MCP_OAUTH_CONFIG_URL", raising=False)
    monkeypatch.delenv("LUNCHMONEY_MCP_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("LUNCHMONEY_MCP_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("LUNCHMONEY_MCP_OAUTH_BASE_URL", raising=False)
    monkeypatch.delenv("LUNCHMONEY_MCP_OAUTH_AUDIENCE", raising=False)
    monkeypatch.delenv("STATELESS", raising=False)
    monkeypatch.delenv("LUNCHMONEY_SYNC_SAFETY_MARGIN_MINUTES", raising=False)
    monkeypatch.delenv("LUNCHMONEY_SCHEDULE_CRON", raising=False)
    monkeypatch.delenv("LUNCHMONEY_SCHEDULE_TIMEZONE", raising=False)
    monkeypatch.delenv("LUNCHMONEY_SCHEDULE_DAYS", raising=False)
    monkeypatch.delenv("LUNCHMONEY_EMBED_SCHEDULER", raising=False)
    monkeypatch.delenv("LUNCHMONEY_HOST", raising=False)
    monkeypatch.delenv("LUNCHMONEY_PORT", raising=False)

    settings = Settings()
    assert settings.lunchmoney_database_url == DEFAULT_DATABASE_URL
    assert settings.redis_url is None
    assert settings.lunchmoney_access_token is None
    assert settings.lunchmoney_mcp_api_key is None
    assert settings.lunchmoney_mcp_oauth_config_url is None
    assert settings.lunchmoney_mcp_oauth_client_id is None
    assert settings.lunchmoney_mcp_oauth_client_secret is None
    assert settings.lunchmoney_mcp_oauth_base_url is None
    assert settings.lunchmoney_mcp_oauth_audience is None
    assert settings.stateless is False
    assert settings.sync_safety_margin_minutes == 5
    assert settings.scheduler_cron == "0 * * * *"
    assert settings.scheduler_timezone == "UTC"
    assert settings.scheduler_days == 30
    assert settings.embedded_scheduler is False
    assert settings.server_host == "127.0.0.1"
    assert settings.server_port == 8000


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
    monkeypatch.setenv("LUNCHMONEY_MCP_API_KEY", "rest-api-key")
    monkeypatch.setenv(
        "LUNCHMONEY_MCP_OAUTH_CONFIG_URL",
        "https://id.example.com/.well-known/openid-configuration",
    )
    monkeypatch.setenv("LUNCHMONEY_MCP_OAUTH_CLIENT_ID", "lunchmoney-mcp")
    monkeypatch.setenv("LUNCHMONEY_MCP_OAUTH_CLIENT_SECRET", "synthetic-secret")
    monkeypatch.setenv("LUNCHMONEY_MCP_OAUTH_BASE_URL", "https://mcp.example.com")
    monkeypatch.setenv("LUNCHMONEY_MCP_OAUTH_AUDIENCE", "https://mcp.example.com")
    monkeypatch.setenv("STATELESS", "true")
    monkeypatch.setenv("LUNCHMONEY_SYNC_SAFETY_MARGIN_MINUTES", "10")
    monkeypatch.setenv("LUNCHMONEY_SCHEDULE_CRON", "15 4 * * 1-5")
    monkeypatch.setenv("LUNCHMONEY_SCHEDULE_TIMEZONE", "America/Denver")
    monkeypatch.setenv("LUNCHMONEY_SCHEDULE_DAYS", "45")
    monkeypatch.setenv("LUNCHMONEY_EMBED_SCHEDULER", "true")
    monkeypatch.setenv("LUNCHMONEY_HOST", "0.0.0.0")
    monkeypatch.setenv("LUNCHMONEY_PORT", "9000")

    settings = Settings()
    assert (
        settings.lunchmoney_database_url
        == "postgresql+asyncpg://user:pass@localhost/db"
    )
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.lunchmoney_access_token == "test-token"
    assert settings.lunchmoney_mcp_api_key == "rest-api-key"
    assert (
        settings.lunchmoney_mcp_oauth_config_url
        == "https://id.example.com/.well-known/openid-configuration"
    )
    assert settings.lunchmoney_mcp_oauth_client_id == "lunchmoney-mcp"
    assert settings.lunchmoney_mcp_oauth_client_secret == "synthetic-secret"
    assert settings.lunchmoney_mcp_oauth_base_url == "https://mcp.example.com"
    assert settings.lunchmoney_mcp_oauth_audience == "https://mcp.example.com"
    assert settings.stateless is True
    assert settings.sync_safety_margin_minutes == 10
    assert settings.scheduler_cron == "15 4 * * 1-5"
    assert settings.scheduler_timezone == "America/Denver"
    assert settings.scheduler_days == 45
    assert settings.embedded_scheduler is True
    assert settings.server_host == "0.0.0.0"
    assert settings.server_port == 9000


def test_settings_parse_runtime_cli_arguments() -> None:
    """Parse scheduler, embedded-server, and bind options from kebab-case CLI flags."""
    settings = parse_cli_settings(
        [
            "--scheduler-cron",
            "15 4 * * 1-5",
            "--scheduler-timezone",
            "America/Denver",
            "--scheduler-days",
            "45",
            "--embedded-scheduler",
            "--server-host",
            "0.0.0.0",
            "--server-port",
            "9000",
        ]
    )

    assert settings.scheduler_cron == "15 4 * * 1-5"
    assert settings.scheduler_timezone == "America/Denver"
    assert settings.scheduler_days == 45
    assert settings.embedded_scheduler is True
    assert settings.server_host == "0.0.0.0"
    assert settings.server_port == 9000


def test_cli_help_only_exposes_lowercase_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep environment-variable aliases out of the CLI help output."""
    with pytest.raises(SystemExit):
        parse_cli_settings(["--help"])

    help_output = capsys.readouterr().out
    assert "--lunchmoney-access-token" in help_output
    assert "--sync-safety-margin-minutes" in help_output
    assert "--LUNCHMONEY-ACCESS-TOKEN" not in help_output
    assert "--LUNCHMONEY-SYNC-SAFETY-MARGIN-MINUTES" not in help_output


def test_export_runtime_settings_preserves_cli_values_for_reloader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Export explicit runtime values into the environment inherited by reloaders."""
    monkeypatch.delenv("LUNCHMONEY_EMBED_SCHEDULER", raising=False)
    monkeypatch.delenv("LUNCHMONEY_HOST", raising=False)
    monkeypatch.delenv("LUNCHMONEY_PORT", raising=False)
    settings = Settings(
        embedded_scheduler=True,
        server_host="0.0.0.0",
        server_port=9000,
    )

    export_runtime_settings(settings)

    assert os.environ["LUNCHMONEY_EMBED_SCHEDULER"] == "true"
    assert os.environ["LUNCHMONEY_HOST"] == "0.0.0.0"
    assert os.environ["LUNCHMONEY_PORT"] == "9000"


def test_mcp_runtime_forces_ephemeral_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent standalone MCP transport processes from opening persistent storage."""
    import lunchmoney_mcp.config as config_module

    monkeypatch.setenv("LUNCHMONEY_DATABASE_URL", "sqlite+aiosqlite:///persistent.db")
    monkeypatch.setattr(config_module, "_runtime_mode", None)
    configure_runtime_mode("mcp")

    assert resolve_database_url() == IN_MEMORY_DATABASE_URL


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


def test_dotenv_default_database_url_overrides_stateless_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Preserve an explicitly configured default URL over stateless mode."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STATELESS", "true")
    monkeypatch.delenv("LUNCHMONEY_DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text(f"LUNCHMONEY_DATABASE_URL={DEFAULT_DATABASE_URL}\n")
    get_settings.cache_clear()

    assert resolve_database_url() == DEFAULT_DATABASE_URL
    get_settings.cache_clear()


def test_get_settings_cached() -> None:
    """Return a cached Settings instance."""
    settings_1 = get_settings()
    settings_2 = get_settings()
    assert settings_1 is settings_2
