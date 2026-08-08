"""Persistent Lunch Money recurring-item definitions."""

from typing import Any, ClassVar

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class RecurringItem(SQLModel, table=True):
    """Store a canonical recurring-item response keyed by its upstream ID."""

    __tablename__: ClassVar[str] = "recurring_items"

    id: int = Field(primary_key=True, index=True)
    """Lunch Money recurring-item identifier."""
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    """Canonical definition and most recently synchronized match data."""
