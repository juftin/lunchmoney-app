"""SQLModel record for Lunch Money tags."""

from datetime import datetime
from typing import ClassVar, Self

from lunchmoney.models import TagObject
from sqlmodel import Field, SQLModel


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
    updated_at: datetime
    """Timestamp when the tag was last updated."""
    created_at: datetime
    """Timestamp when the tag was created."""
    archived: bool
    """Whether the tag is archived."""
    archived_at: datetime | None
    """Optional timestamp when the tag was archived."""

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
            created_at=model.created_at,
            archived=model.archived,
            archived_at=model.archived_at,
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
                "updated_at": self.updated_at,
                "created_at": self.created_at,
                "archived": self.archived,
                "archived_at": self.archived_at,
            }
        )
