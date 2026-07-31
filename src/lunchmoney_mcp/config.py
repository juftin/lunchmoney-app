"""Application configuration and settings using Pydantic Settings."""

from functools import cache
import os
from typing import Any, Literal, cast

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, CliSettingsSource, SettingsConfigDict

DEFAULT_DATABASE_URL: str = "sqlite+aiosqlite:///lunchmoney.db"
"""Default persistent SQLite connection URL used when omitted."""

IN_MEMORY_DATABASE_URL: str = (
    "sqlite+aiosqlite:///file:memdb?mode=memory&cache=shared&uri=true"
)
"""Shared in-memory SQLite connection URL used by stateless mode."""


class LowercaseCliSettingsSource(CliSettingsSource):
    """Expose only lowercase option names while retaining uppercase environment aliases."""

    def _get_arg_names(self, *args: Any, **kwargs: Any) -> list[str]:
        """Return the lowercase flags generated for a settings field."""
        return [
            argument_name
            for argument_name in super()._get_arg_names(*args, **kwargs)
            if argument_name == argument_name.lower()
        ]


class Settings(BaseSettings):
    """Lunch Money MCP application settings.

    Attributes
    ----------
    lunchmoney_access_token : str | None
        Lunch Money API access token.
    lunchmoney_mcp_api_key : str | None
        Optional key required by this project's REST API.
    lunchmoney_mcp_oauth_config_url : str | None
        OIDC discovery URL for remote MCP client authentication.
    lunchmoney_mcp_oauth_client_id : str | None
        OAuth client identifier registered with the upstream identity provider.
    lunchmoney_mcp_oauth_client_secret : str | None
        Optional OAuth client secret for confidential identity-provider clients.
    lunchmoney_mcp_oauth_base_url : str | None
        Public base URL used for OAuth metadata and callback routes.
    lunchmoney_mcp_oauth_audience : str | None
        Optional OAuth audience requested from the identity provider.
    lunchmoney_database_url : str
        Database connection URL (sqlite+aiosqlite or postgresql+asyncpg).
    redis_url : str | None
        Redis connection URL for distributed locking.
    environment : str
        Application deployment environment name.
    stateless : bool
        Whether to use the shared in-memory database.
    sync_safety_margin_minutes : int
        Safety overlap margin for incremental ETL queries.
    scheduler_cron : str
        Cron expression used by the opt-in scheduler process.
    scheduler_timezone : str
        IANA timezone used to interpret the scheduler cron expression.
    scheduler_days : int
        Rolling transaction window used by the scheduler's initial sync.
    embedded_scheduler : bool
        Whether a local single-process FastAPI server starts a scheduler in its lifespan.
    server_host : str
        Interface used by the local FastAPI serve command.
    server_port : int
        Port used by the local FastAPI serve command.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        cli_kebab_case=True,
        cli_implicit_flags=True,
    )

    lunchmoney_access_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LUNCHMONEY_ACCESS_TOKEN", "lunchmoney_access_token"
        ),
        description="Lunch Money API access token",
    )
    """Lunch Money API access token."""

    lunchmoney_mcp_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LUNCHMONEY_MCP_API_KEY", "lunchmoney_mcp_api_key"
        ),
        description="Optional API key required by the Lunch Money MCP REST API",
    )
    """Optional API key required by the Lunch Money MCP REST API."""

    lunchmoney_mcp_oauth_config_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LUNCHMONEY_MCP_OAUTH_CONFIG_URL", "lunchmoney_mcp_oauth_config_url"
        ),
        description="OIDC discovery URL for remote MCP client authentication",
    )
    """OIDC discovery URL for remote MCP client authentication."""

    lunchmoney_mcp_oauth_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LUNCHMONEY_MCP_OAUTH_CLIENT_ID", "lunchmoney_mcp_oauth_client_id"
        ),
        description="OAuth client identifier registered with the identity provider",
    )
    """OAuth client identifier registered with the identity provider."""

    lunchmoney_mcp_oauth_client_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LUNCHMONEY_MCP_OAUTH_CLIENT_SECRET", "lunchmoney_mcp_oauth_client_secret"
        ),
        description="Optional OAuth client secret for confidential clients",
    )
    """Optional OAuth client secret for confidential clients."""

    lunchmoney_mcp_oauth_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LUNCHMONEY_MCP_OAUTH_BASE_URL", "lunchmoney_mcp_oauth_base_url"
        ),
        description="Public base URL used for OAuth metadata and callback routes",
    )
    """Public base URL used for OAuth metadata and callback routes."""

    lunchmoney_mcp_oauth_audience: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LUNCHMONEY_MCP_OAUTH_AUDIENCE", "lunchmoney_mcp_oauth_audience"
        ),
        description="Optional OAuth audience requested from the identity provider",
    )
    """Optional OAuth audience requested from the identity provider."""

    lunchmoney_database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        validation_alias=AliasChoices(
            "LUNCHMONEY_DATABASE_URL", "lunchmoney_database_url"
        ),
        description="Database connection URL (sqlite+aiosqlite or postgresql+asyncpg)",
    )
    """Database connection URL."""

    redis_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_URL", "redis_url"),
        description="Redis connection URL for distributed locking",
    )
    """Redis connection URL for distributed locking."""

    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "environment"),
        description="Application deployment environment",
    )
    """Application deployment environment name."""

    stateless: bool = Field(
        default=False,
        validation_alias=AliasChoices("STATELESS", "stateless"),
        description="Run in stateless mode using in-memory SQLite database refreshed from API",
    )
    """Whether to use the shared in-memory database."""

    sync_safety_margin_minutes: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "LUNCHMONEY_SYNC_SAFETY_MARGIN_MINUTES", "sync_safety_margin_minutes"
        ),
        description="Safety overlap margin in minutes for incremental ETL queries",
    )
    """Safety overlap margin for incremental ETL queries."""

    scheduler_cron: str = Field(
        default="0 * * * *",
        validation_alias=AliasChoices("LUNCHMONEY_SCHEDULE_CRON", "scheduler_cron"),
        description="Cron expression used by the opt-in scheduler process",
    )
    """Cron expression used by the opt-in scheduler process."""

    scheduler_timezone: str = Field(
        default="UTC",
        validation_alias=AliasChoices(
            "LUNCHMONEY_SCHEDULE_TIMEZONE", "scheduler_timezone"
        ),
        description="IANA timezone used to interpret the scheduler cron expression",
    )
    """IANA timezone used to interpret the scheduler cron expression."""

    scheduler_days: int = Field(
        default=30,
        ge=1,
        validation_alias=AliasChoices("LUNCHMONEY_SCHEDULE_DAYS", "scheduler_days"),
        description="Rolling transaction window used by the scheduler's initial sync",
    )
    """Rolling transaction window used by the scheduler's initial sync."""

    embedded_scheduler: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "LUNCHMONEY_EMBED_SCHEDULER", "embedded_scheduler"
        ),
        description="Start the local scheduler from the FastAPI application lifespan",
    )
    """Whether a local single-process FastAPI server starts an embedded scheduler."""

    server_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("LUNCHMONEY_HOST", "server_host"),
        description="Interface used by the local FastAPI serve command",
    )
    """Interface used by the local FastAPI serve command."""

    server_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("LUNCHMONEY_PORT", "server_port"),
        description="Port used by the local FastAPI serve command",
    )
    """Port used by the local FastAPI serve command."""


_runtime_settings: Settings | None = None
"""Process-local Settings supplied by a runtime command's Pydantic CLI parser."""

RuntimeMode = Literal["mcp", "schedule", "serve"]
"""The dedicated runtime command currently executing in this process."""

_runtime_mode: RuntimeMode | None = None
"""Process-local runtime mode used to enforce command-level responsibilities."""


def parse_cli_settings(
    arguments: list[str],
    root_parser: Any | None = None,
) -> Settings:
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
    Settings
        Configuration populated from CLI flags, environment variables, and `.env`.
    """
    source = LowercaseCliSettingsSource(
        Settings,
        cli_parse_args=arguments,
        root_parser=root_parser,
    )
    return cast(Any, Settings)(_cli_settings_source=source)


def configure_runtime_settings(settings: Settings) -> None:
    """Make CLI-parsed settings available to the current runtime process.

    Parameters
    ----------
    settings : Settings
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


def export_runtime_settings(settings: Settings) -> None:
    """Expose non-default runtime settings to a Uvicorn reloader child.

    Parameters
    ----------
    settings : Settings
        Resolved runtime configuration. Only values supplied by a configuration
        source are exported; defaults remain defaults in the child process.
    """
    for field_name in settings.model_fields_set:
        field = Settings.model_fields[field_name]
        alias = field.validation_alias
        if not isinstance(alias, AliasChoices):
            continue
        environment_name = alias.choices[0]
        if not isinstance(environment_name, str):
            continue
        value = getattr(settings, field_name)
        if value is None:
            os.environ.pop(environment_name, None)
        elif isinstance(value, bool):
            os.environ[environment_name] = str(value).lower()
        else:
            os.environ[environment_name] = str(value)


@cache
def get_settings() -> Settings:
    """Return a cached application settings instance.

    Returns
    -------
    Settings
        Cached application configuration object populated from a runtime CLI or environment.
    """
    return _runtime_settings or Settings()
