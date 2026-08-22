"""Persistent snapshots for upstream responses without relational models."""

from typing import Any, ClassVar

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class CachedApiResponse(SQLModel, table=True):
    """Store one canonical API response under a stable cache key."""

    __tablename__: ClassVar[str] = "cached_api_responses"

    key: str = Field(primary_key=True)
    """Stable resource or period-and-options cache key."""
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    """JSON-compatible canonical upstream response."""
