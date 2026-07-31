"""Application configuration and settings using Pydantic Settings."""

from functools import cache
import os
from typing import Any, Literal, cast

from pydantic import Field
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

DEFAULT_DATABASE_URL: str = "sqlite+aiosqlite:///lunchmoney.db"
"""Default persistent SQLite connection URL used when omitted."""

IN_MEMORY_DATABASE_URL: str = (
    "sqlite+aiosqlite:///file:memdb?mode=memory&cache=shared&uri=true"
)
"""Shared in-memory SQLite connection URL used by stateless mode."""

ENVIRONMENT_VARIABLE_NAMES: dict[str, str] = {
    "lunchmoney_access_token": "LUNCHMONEY_ACCESS_TOKEN",
    "lunchmoney_mcp_api_key": "LUNCHMONEY_MCP_API_KEY",
    "lunchmoney_mcp_oauth_config_url": "LUNCHMONEY_MCP_OAUTH_CONFIG_URL",
    "lunchmoney_mcp_oauth_client_id": "LUNCHMONEY_MCP_OAUTH_CLIENT_ID",
    "lunchmoney_mcp_oauth_client_secret": "LUNCHMONEY_MCP_OAUTH_CLIENT_SECRET",
    "lunchmoney_mcp_oauth_base_url": "LUNCHMONEY_MCP_OAUTH_BASE_URL",
    "lunchmoney_mcp_oauth_audience": "LUNCHMONEY_MCP_OAUTH_AUDIENCE",
    "lunchmoney_database_url": "LUNCHMONEY_DATABASE_URL",
    "redis_url": "REDIS_URL",
    "environment": "ENVIRONMENT",
    "stateless": "STATELESS",
    "sync_safety_margin_minutes": "LUNCHMONEY_SYNC_SAFETY_MARGIN_MINUTES",
    "scheduler_cron": "LUNCHMONEY_SCHEDULE_CRON",
    "scheduler_timezone": "LUNCHMONEY_SCHEDULE_TIMEZONE",
    "scheduler_days": "LUNCHMONEY_SCHEDULE_DAYS",
    "embedded_scheduler": "LUNCHMONEY_EMBED_SCHEDULER",
    "server_host": "LUNCHMONEY_HOST",
    "server_port": "LUNCHMONEY_PORT",
}
"""Canonical environment variable names for application settings."""


def _get_environment_variable_value(
    source: EnvSettingsSource,
    field_name: str,
) -> tuple[Any, str, bool] | None:
    """Retrieve the canonical environment variable value for a settings field."""
    environment_variable = ENVIRONMENT_VARIABLE_NAMES.get(field_name)
    if environment_variable is None:
        return None

    environment_name = (
        environment_variable if source.case_sensitive else environment_variable.lower()
    )
    value = source.env_vars.get(environment_name)
    if value is None:
        return None
    return value, field_name, False


class LunchMoneyEnvSettingsSource(EnvSettingsSource):
    """Load settings from their documented environment variable names."""

    def get_field_value(
        self,
        field: FieldInfo,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        """Prefer a documented environment variable before default field lookup."""
        environment_value = _get_environment_variable_value(self, field_name)
        if environment_value is not None:
            return environment_value
        return super().get_field_value(field, field_name)


class LunchMoneyDotEnvSettingsSource(DotEnvSettingsSource):
    """Load settings from documented names in the configured dotenv file."""

    def get_field_value(
        self,
        field: FieldInfo,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        """Prefer a documented dotenv variable before default field lookup."""
        environment_value = _get_environment_variable_value(self, field_name)
        if environment_value is not None:
            return environment_value
        return super().get_field_value(field, field_name)


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
        description="Lunch Money API access token",
    )
    """Lunch Money API access token."""

    lunchmoney_mcp_api_key: str | None = Field(
        default=None,
        description="Optional API key required by the Lunch Money MCP REST API",
    )
    """Optional API key required by the Lunch Money MCP REST API."""

    lunchmoney_mcp_oauth_config_url: str | None = Field(
        default=None,
        description="OIDC discovery URL for remote MCP client authentication",
    )
    """OIDC discovery URL for remote MCP client authentication."""

    lunchmoney_mcp_oauth_client_id: str | None = Field(
        default=None,
        description="OAuth client identifier registered with the identity provider",
    )
    """OAuth client identifier registered with the identity provider."""

    lunchmoney_mcp_oauth_client_secret: str | None = Field(
        default=None,
        description="Optional OAuth client secret for confidential clients",
    )
    """Optional OAuth client secret for confidential clients."""

    lunchmoney_mcp_oauth_base_url: str | None = Field(
        default=None,
        description="Public base URL used for OAuth metadata and callback routes",
    )
    """Public base URL used for OAuth metadata and callback routes."""

    lunchmoney_mcp_oauth_audience: str | None = Field(
        default=None,
        description="Optional OAuth audience requested from the identity provider",
    )
    """Optional OAuth audience requested from the identity provider."""

    lunchmoney_database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        description="Database connection URL (sqlite+aiosqlite or postgresql+asyncpg)",
    )
    """Database connection URL."""

    redis_url: str | None = Field(
        default=None,
        description="Redis connection URL for distributed locking",
    )
    """Redis connection URL for distributed locking."""

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

    scheduler_cron: str = Field(
        default="0 * * * *",
        description="Cron expression used by the opt-in scheduler process",
    )
    """Cron expression used by the opt-in scheduler process."""

    scheduler_timezone: str = Field(
        default="UTC",
        description="IANA timezone used to interpret the scheduler cron expression",
    )
    """IANA timezone used to interpret the scheduler cron expression."""

    scheduler_days: int = Field(
        default=30,
        ge=1,
        description="Rolling transaction window used by the scheduler's initial sync",
    )
    """Rolling transaction window used by the scheduler's initial sync."""

    embedded_scheduler: bool = Field(
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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Use sources that preserve the documented environment variable names."""
        return (
            init_settings,
            LunchMoneyEnvSettingsSource(settings_cls),
            LunchMoneyDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )


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
    source = CliSettingsSource(
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
        environment_name = ENVIRONMENT_VARIABLE_NAMES.get(field_name)
        if environment_name is None:
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
