"""Application configuration and settings using Pydantic Settings."""

from functools import cache
from ipaddress import ip_address
import os
from typing import Any, Literal, cast

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, CliSettingsSource, SettingsConfigDict

DEFAULT_DATABASE_URL: str = "sqlite+aiosqlite:///lunchmoney.db"
"""Default persistent SQLite connection URL used when omitted."""

IN_MEMORY_DATABASE_URL: str = (
    "sqlite+aiosqlite:///file:memdb?mode=memory&cache=shared&uri=true"
)
"""Shared in-memory SQLite connection URL used by stateless mode."""


def _split_comma_separated_values(value: str) -> tuple[str, ...]:
    """Normalize a comma-separated network policy value.

    Parameters
    ----------
    value : str
        Comma-separated configuration value supplied by the environment or CLI.

    Returns
    -------
    tuple[str, ...]
        Non-empty, whitespace-trimmed policy entries in their configured order.
    """
    return tuple(item.strip() for item in value.split(",") if item.strip())


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
    trusted_proxy_ips : str
        Comma-separated proxy IP addresses trusted to supply forwarding headers.
    allowed_hosts : str
        Comma-separated public hostnames accepted by the HTTP server.
    cors_allowed_origins : str
        Comma-separated browser origins authorized for cross-origin requests.
    max_request_body_bytes : int
        Maximum permitted HTTP request body size in bytes.
    request_timeout_seconds : float
        Maximum permitted HTTP request duration in seconds.
    max_concurrent_requests : int
        Maximum in-flight HTTP requests accepted by a process.
    rate_limit_requests : int
        Maximum requests accepted from one client during the rate-limit window.
    rate_limit_window_seconds : int
        Duration of the fixed rate-limit window in seconds.
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

    trusted_proxy_ips: str = Field(
        default="",
        validation_alias=AliasChoices(
            "LUNCHMONEY_TRUSTED_PROXY_IPS", "trusted_proxy_ips"
        ),
        description=(
            "Comma-separated proxy IP addresses trusted to supply forwarding headers; "
            "empty disables proxy trust"
        ),
    )
    """Comma-separated trusted proxy IP addresses; empty disables proxy trust."""

    allowed_hosts: str = Field(
        default="localhost,127.0.0.1",
        validation_alias=AliasChoices("LUNCHMONEY_ALLOWED_HOSTS", "allowed_hosts"),
        description="Comma-separated HTTP Host header allow-list",
    )
    """Comma-separated public hostnames accepted by the HTTP server."""

    cors_allowed_origins: str = Field(
        default="",
        validation_alias=AliasChoices(
            "LUNCHMONEY_CORS_ALLOWED_ORIGINS", "cors_allowed_origins"
        ),
        description=(
            "Comma-separated browser origins authorized for CORS; empty disables CORS"
        ),
    )
    """Comma-separated CORS origin allow-list; empty disables CORS."""

    max_request_body_bytes: int = Field(
        default=1_048_576,
        ge=1,
        validation_alias=AliasChoices(
            "LUNCHMONEY_MAX_REQUEST_BODY_BYTES", "max_request_body_bytes"
        ),
        description="Maximum accepted HTTP request body size in bytes",
    )
    """Maximum accepted HTTP request body size in bytes."""

    request_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        validation_alias=AliasChoices(
            "LUNCHMONEY_REQUEST_TIMEOUT_SECONDS", "request_timeout_seconds"
        ),
        description="Maximum accepted HTTP request duration in seconds",
    )
    """Maximum accepted HTTP request duration in seconds."""

    max_concurrent_requests: int = Field(
        default=100,
        ge=1,
        validation_alias=AliasChoices(
            "LUNCHMONEY_MAX_CONCURRENT_REQUESTS", "max_concurrent_requests"
        ),
        description="Maximum in-flight HTTP requests per process",
    )
    """Maximum in-flight HTTP requests accepted by a process."""

    rate_limit_requests: int = Field(
        default=120,
        ge=1,
        validation_alias=AliasChoices(
            "LUNCHMONEY_RATE_LIMIT_REQUESTS", "rate_limit_requests"
        ),
        description="Maximum requests per client in each rate-limit window",
    )
    """Maximum requests accepted from one client during the rate-limit window."""

    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        validation_alias=AliasChoices(
            "LUNCHMONEY_RATE_LIMIT_WINDOW_SECONDS", "rate_limit_window_seconds"
        ),
        description="Fixed rate-limit window duration in seconds",
    )
    """Duration of the fixed rate-limit window in seconds."""

    @field_validator("trusted_proxy_ips")
    @classmethod
    def _validate_trusted_proxy_ips(cls, value: str) -> str:
        """Accept only explicit proxy IP addresses for forwarding-header trust."""
        addresses = _split_comma_separated_values(value)
        for address in addresses:
            ip_address(address)
        return ",".join(addresses)

    @field_validator("allowed_hosts")
    @classmethod
    def _validate_allowed_hosts(cls, value: str) -> str:
        """Require a concrete Host header allow-list without wildcards."""
        hosts = _split_comma_separated_values(value)
        if not hosts:
            msg = "allowed_hosts must contain at least one host"
            raise ValueError(msg)
        if "*" in hosts:
            msg = "allowed_hosts must not contain a wildcard"
            raise ValueError(msg)
        return ",".join(hosts)

    @field_validator("cors_allowed_origins")
    @classmethod
    def _validate_cors_allowed_origins(cls, value: str) -> str:
        """Normalize CORS origins while refusing the insecure wildcard origin."""
        origins = _split_comma_separated_values(value)
        if "*" in origins:
            msg = "cors_allowed_origins must not contain a wildcard"
            raise ValueError(msg)
        return ",".join(origins)

    @property
    def trusted_proxy_ip_list(self) -> tuple[str, ...]:
        """Return the proxy IP allow-list in middleware-friendly form."""
        return _split_comma_separated_values(self.trusted_proxy_ips)

    @property
    def allowed_host_list(self) -> tuple[str, ...]:
        """Return the HTTP Host header allow-list in middleware-friendly form."""
        return _split_comma_separated_values(self.allowed_hosts)

    @property
    def cors_allowed_origin_list(self) -> tuple[str, ...]:
        """Return the CORS origin allow-list in middleware-friendly form."""
        return _split_comma_separated_values(self.cors_allowed_origins)


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
