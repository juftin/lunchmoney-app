"""Application configuration and settings using Pydantic Settings."""

from functools import cache
import os
from typing import Any, Literal, cast

from pydantic import Field
from pydantic_settings import BaseSettings, CliSettingsSource, SettingsConfigDict

DEFAULT_DATABASE_URL: str = "sqlite+aiosqlite:///lunchmoney.db"
"""Default persistent SQLite connection URL used when omitted."""

IN_MEMORY_DATABASE_URL: str = (
    "sqlite+aiosqlite:///file:memdb?mode=memory&cache=shared&uri=true"
)
"""Shared in-memory SQLite connection URL used by stateless mode."""


class SecretSettings(BaseSettings):
    """Environment-only settings that can contain credentials.

    Attributes
    ----------
    access_token : str | None
        Lunch Money API access token.
    mcp_api_key : str | None
        Optional key required by this project's REST API.
    mcp_oauth_client_secret : str | None
        Optional OAuth client secret for confidential identity-provider clients.
    database_url : str
        Database connection URL (sqlite+aiosqlite or postgresql+asyncpg).
    redis_url : str | None
        Redis connection URL for distributed locking.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LUNCHMONEY_",
        extra="ignore",
    )

    access_token: str | None = Field(
        default=None,
        description="Lunch Money API access token",
    )
    """Lunch Money API access token."""

    mcp_api_key: str | None = Field(
        default=None,
        description="Optional API key required by the Lunch Money MCP REST API",
    )
    """Optional API key required by the Lunch Money MCP REST API."""

    mcp_oauth_client_secret: str | None = Field(
        default=None,
        description="Optional OAuth client secret for confidential clients",
    )
    """Optional OAuth client secret for confidential clients."""

    database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        description="Database connection URL (sqlite+aiosqlite or postgresql+asyncpg)",
    )
    """Database connection URL."""

    redis_url: str | None = Field(
        default=None,
        description="Redis connection URL for distributed locking",
    )
    """Redis connection URL for distributed locking."""


class RuntimeSettings(BaseSettings):
    """Environment and CLI settings that do not contain credentials."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LUNCHMONEY_",
        extra="ignore",
        cli_kebab_case=True,
        cli_implicit_flags=True,
    )

    mcp_oauth_config_url: str | None = Field(
        default=None,
        description="OIDC discovery URL for remote MCP client authentication",
    )
    """OIDC discovery URL for remote MCP client authentication."""

    mcp_oauth_client_id: str | None = Field(
        default=None,
        description="OAuth client identifier registered with the identity provider",
    )
    """OAuth client identifier registered with the identity provider."""

    mcp_oauth_base_url: str | None = Field(
        default=None,
        description="Public base URL used for OAuth metadata and callback routes",
    )
    """Public base URL used for OAuth metadata and callback routes."""

    mcp_oauth_audience: str | None = Field(
        default=None,
        description="Optional OAuth audience requested from the identity provider",
    )
    """Optional OAuth audience requested from the identity provider."""

    environment: str = Field(
        default="development",
        description="Application deployment environment",
    )
    """Application deployment environment name."""

    stateless: bool = Field(
        default=False,
        description="Run in stateless mode using in-memory SQLite database refreshed from API",
    )
    """Whether to use the shared in-memory database."""

    sync_safety_margin_minutes: int = Field(
        default=5,
        description="Safety overlap margin in minutes for incremental ETL queries",
    )
    """Safety overlap margin for incremental ETL queries."""

    schedule_cron: str = Field(
        default="0 * * * *",
        description="Cron expression used by the opt-in scheduler process",
    )
    """Cron expression used by the opt-in scheduler process."""

    schedule_timezone: str = Field(
        default="UTC",
        description="IANA timezone used to interpret the scheduler cron expression",
    )
    """IANA timezone used to interpret the scheduler cron expression."""

    schedule_days: int = Field(
        default=30,
        ge=1,
        description="Rolling transaction window used by the scheduler's initial sync",
    )
    """Rolling transaction window used by the scheduler's initial sync."""

    embed_scheduler: bool = Field(
        default=False,
        description="Start the local scheduler from the FastAPI application lifespan",
    )
    """Whether a local single-process FastAPI server starts an embedded scheduler."""

    server_host: str = Field(
        default="127.0.0.1",
        description="Interface used by the local FastAPI serve command",
    )
    """Interface used by the local FastAPI serve command."""

    server_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port used by the local FastAPI serve command",
    )
    """Port used by the local FastAPI serve command."""


_runtime_settings: RuntimeSettings | None = None
"""Process-local runtime settings supplied by Pydantic's CLI parser."""

RuntimeMode = Literal["mcp", "schedule", "serve"]
"""The dedicated runtime command currently executing in this process."""

_runtime_mode: RuntimeMode | None = None
"""Process-local runtime mode used to enforce command-level responsibilities."""


def parse_cli_settings(
    arguments: list[str],
    root_parser: Any | None = None,
) -> RuntimeSettings:
    """Parse runtime options with Pydantic Settings' native CLI source.

    Parameters
    ----------
    arguments : list[str]
        Kebab-case Pydantic Settings arguments without an executable or subcommand.
    root_parser : Any | None
        Optional parser with runtime-specific arguments that Pydantic extends with
        Settings options before parsing.

    Returns
    -------
    RuntimeSettings
        Non-secret configuration populated from CLI flags, environment variables, and `.env`.
    """
    source = CliSettingsSource(
        RuntimeSettings,
        cli_parse_args=arguments,
        root_parser=root_parser,
    )
    return cast(Any, RuntimeSettings)(_cli_settings_source=source)


def configure_runtime_settings(settings: RuntimeSettings) -> None:
    """Make CLI-parsed settings available to the current runtime process.

    Parameters
    ----------
    settings : RuntimeSettings
        Configuration parsed before the FastAPI or scheduler runtime starts.
    """
    global _runtime_settings
    _runtime_settings = settings
    get_settings.cache_clear()


def configure_runtime_mode(mode: RuntimeMode) -> None:
    """Record the command mode that owns the current process.

    Parameters
    ----------
    mode : RuntimeMode
        Runtime command selected by the executable.
    """
    global _runtime_mode
    _runtime_mode = mode


def get_runtime_mode() -> RuntimeMode | None:
    """Return the command mode selected for the current process.

    Returns
    -------
    RuntimeMode | None
        Selected runtime mode, or ``None`` outside the executable dispatcher.
    """
    return _runtime_mode


def export_runtime_settings(settings: RuntimeSettings) -> None:
    """Expose non-default runtime settings to a Uvicorn reloader child.

    Parameters
    ----------
    settings : RuntimeSettings
        Resolved runtime configuration. Only values supplied by a configuration
        source are exported; defaults remain defaults in the child process.
    """
    for field_name in settings.model_fields_set:
        environment_name = f"LUNCHMONEY_{field_name.upper()}"
        value = getattr(settings, field_name)
        if value is None:
            os.environ.pop(environment_name, None)
        elif isinstance(value, bool):
            os.environ[environment_name] = str(value).lower()
        else:
            os.environ[environment_name] = str(value)


@cache
def get_settings() -> RuntimeSettings:
    """Return cached non-secret runtime settings.

    Returns
    -------
    RuntimeSettings
        Cached non-secret configuration populated from a runtime CLI or environment.
    """
    return _runtime_settings or RuntimeSettings()


@cache
def get_secret_settings() -> SecretSettings:
    """Return cached environment-only secret settings."""
    return SecretSettings()
