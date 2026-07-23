"""SQLModel record for Lunch Money tags."""

from datetime import datetime
from builtins import type as builtin_type
from typing import Any, ClassVar, Self, cast

from lunchmoney.models import TagObject
from sqlmodel import Field, SQLModel

from lunchmoney_mcp.database.models._datetime import (
    UTCDateTime,
    datetime_offset_minutes,
    restore_datetime_shape,
)


class Tag(SQLModel, table=True):
    """Persist every scalar field from a generated tag object."""

    __tablename__: ClassVar[str] = "tags"

    id: int = Field(primary_key=True, index=True)
    """Lunch Money tag identifier."""
    name: str
    """Tag display name."""
    description: str | None
    """Optional tag description."""
    text_color: str | None
    """Optional tag text color."""
    background_color: str | None
    """Optional tag background color."""
    updated_at: datetime = Field(sa_type=cast(builtin_type[Any], UTCDateTime()))
    """Timestamp when the tag was last updated."""
    updated_at_offset_minutes: int | None = None
    """Source update timestamp offset, or ``None`` when it was naive."""
    created_at: datetime = Field(sa_type=cast(builtin_type[Any], UTCDateTime()))
    """Timestamp when the tag was created."""
    created_at_offset_minutes: int | None = None
    """Source creation timestamp offset, or ``None`` when it was naive."""
    archived: bool
    """Whether the tag is archived."""
    archived_at: datetime | None = Field(sa_type=cast(builtin_type[Any], UTCDateTime()))
    """Optional timestamp when the tag was archived."""
    archived_at_offset_minutes: int | None = None
    """Source archive timestamp offset, or ``None`` when it was naive."""

    @classmethod
    def from_api(cls, model: TagObject) -> Self:
        """Create a database tag from a generated API object.

        Parameters
        ----------
        model
            Generated Lunch Money tag object to convert.

        Returns
        -------
        Self
            Database record containing every generated scalar field.
        """
        return cls(
            id=model.id,
            name=model.name,
            description=model.description,
            text_color=model.text_color,
            background_color=model.background_color,
            updated_at=model.updated_at,
            updated_at_offset_minutes=datetime_offset_minutes(model.updated_at),
            created_at=model.created_at,
            created_at_offset_minutes=datetime_offset_minutes(model.created_at),
            archived=model.archived,
            archived_at=model.archived_at,
            archived_at_offset_minutes=datetime_offset_minutes(model.archived_at),
        )

    def to_api(self) -> TagObject:
        """Reconstruct the generated tag API object.

        Returns
        -------
        TagObject
            Generated object with values from this database record.
        """
        return TagObject.model_validate(
            {
                "id": self.id,
                "name": self.name,
                "description": self.description,
                "text_color": self.text_color,
                "background_color": self.background_color,
                "updated_at": restore_datetime_shape(
                    self.updated_at,
                    offset_minutes=self.updated_at_offset_minutes,
                ),
                "created_at": restore_datetime_shape(
                    self.created_at,
                    offset_minutes=self.created_at_offset_minutes,
                ),
                "archived": self.archived,
                "archived_at": restore_datetime_shape(
                    self.archived_at,
                    offset_minutes=self.archived_at_offset_minutes,
                ),
            }
        )
