"""Application configuration and settings using Pydantic Settings."""

from functools import cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL: str = "sqlite+aiosqlite:///lunchmoney.db"
"""Default persistent SQLite connection URL used when omitted."""

IN_MEMORY_DATABASE_URL: str = (
    "sqlite+aiosqlite:///file:memdb?mode=memory&cache=shared&uri=true"
)
"""Shared in-memory SQLite connection URL used by stateless mode."""


class Settings(BaseSettings):
    """Lunch Money MCP application settings.

    Attributes
    ----------
    lunchmoney_access_token : str | None
        Lunch Money API access token.
    lunchmoney_mcp_api_key : str | None
        Optional key required by this project's REST API.
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
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    lunchmoney_access_token: str | None = Field(
        default=None,
        validation_alias="LUNCHMONEY_ACCESS_TOKEN",
        description="Lunch Money API access token",
    )
    """Lunch Money API access token."""

    lunchmoney_mcp_api_key: str | None = Field(
        default=None,
        validation_alias="LUNCHMONEY_MCP_API_KEY",
        description="Optional API key required by the Lunch Money MCP REST API",
    )
    """Optional API key required by the Lunch Money MCP REST API."""

    lunchmoney_database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        validation_alias="LUNCHMONEY_DATABASE_URL",
        description="Database connection URL (sqlite+aiosqlite or postgresql+asyncpg)",
    )
    """Database connection URL."""

    redis_url: str | None = Field(
        default=None,
        validation_alias="REDIS_URL",
        description="Redis connection URL for distributed locking",
    )
    """Redis connection URL for distributed locking."""

    environment: str = Field(
        default="development",
        validation_alias="ENVIRONMENT",
        description="Application deployment environment",
    )
    """Application deployment environment name."""

    stateless: bool = Field(
        default=False,
        validation_alias="STATELESS",
        description="Run in stateless mode using in-memory SQLite database refreshed from API",
    )
    """Whether to use the shared in-memory database."""

    sync_safety_margin_minutes: int = Field(
        default=5,
        validation_alias="LUNCHMONEY_SYNC_SAFETY_MARGIN_MINUTES",
        description="Safety overlap margin in minutes for incremental ETL queries",
    )
    """Safety overlap margin for incremental ETL queries."""


@cache
def get_settings() -> Settings:
    """Return a cached application settings instance.

    Returns
    -------
    Settings
        Cached application configuration object populated from environment.
    """
    return Settings()
