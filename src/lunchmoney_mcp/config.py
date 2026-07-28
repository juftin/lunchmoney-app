"""Application configuration and settings using Pydantic Settings."""

from functools import cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL: str = "sqlite+aiosqlite:///lunchmoney.db"
"""Default persistent SQLite connection URL used when omitted."""


class Settings(BaseSettings):
    """Lunch Money MCP application settings.

    Attributes
    ----------
    lunchmoney_access_token : str | None
        Lunch Money API access token.
    lunchmoney_database_url : str
        Database connection URL (sqlite+aiosqlite or postgresql+asyncpg).
    redis_url : str | None
        Redis connection URL for distributed locking.
    environment : str
        Application deployment environment name.
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


@cache
def get_settings() -> Settings:
    """Return a cached application settings instance.

    Returns
    -------
    Settings
        Cached application configuration object populated from environment.
    """
    return Settings()
