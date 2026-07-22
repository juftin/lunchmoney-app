"""Normalized SQLModel records for Lunch Money category graphs."""

from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar, Optional, Self

from lunchmoney.models import CategoryObject, ChildCategoryObject
from sqlalchemy import String
from sqlmodel import Field, Relationship, SQLModel


class CategoryKind(StrEnum):
    """Identify which generated category schema a row represents."""

    PARENT = "parent"
    """A top-level generated category object."""
    CHILD = "child"
    """A generated child category nested beneath a parent."""


class Category(SQLModel, table=True):
    """Persist parent and child categories as an owned self-referencing graph."""

    __tablename__: ClassVar[str] = "categories"

    id: int = Field(primary_key=True, index=True)
    """Lunch Money category identifier."""
    name: str
    """Category display name."""
    description: str | None
    """Optional category description."""
    is_income: bool
    """Whether the category represents income."""
    exclude_from_budget: bool
    """Whether the category is excluded from budget calculations."""
    exclude_from_totals: bool
    """Whether the category is excluded from aggregate totals."""
    updated_at: datetime
    """Timestamp when the category was last updated."""
    created_at: datetime
    """Timestamp when the category was created."""
    group_id: int | None = Field(foreign_key="categories.id")
    """Optional identifier of this child category's owning parent."""
    is_group: bool
    """Whether the category groups child categories."""
    archived: bool
    """Whether the category is archived."""
    archived_at: datetime | None
    """Optional timestamp when the category was archived."""
    order: int | None
    """Optional display order supplied by Lunch Money."""
    collapsed: bool | None
    """Optional collapsed state shared by the generated category schemas."""
    kind: CategoryKind = Field(sa_type=String)
    """Generated schema represented by this normalized row."""

    parent: Optional["Category"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={
            "foreign_keys": "Category.group_id",
            "remote_side": "Category.id",
        },
    )
    """Owning parent for a child category row."""
    children: list["Category"] = Relationship(
        back_populates="parent",
        cascade_delete=True,
        sa_relationship_kwargs={
            "foreign_keys": "Category.group_id",
            "order_by": ("Category.order.asc().nulls_first(), Category.name.asc()"),
            "single_parent": True,
        },
    )
    """Ordered child category rows owned by this parent."""

    @classmethod
    def from_api(cls, model: CategoryObject) -> Self:
        """Create a normalized category graph from a generated parent object.

        Parameters
        ----------
        model
            Generated Lunch Money category and its optional children.

        Returns
        -------
        Self
            Parent record with owned child records in API order.
        """
        record = cls._from_api_model(
            model,
            kind=CategoryKind.PARENT,
            group_id=model.group_id,
        )
        record.children = [
            cls._from_api_model(
                child,
                kind=CategoryKind.CHILD,
                group_id=model.id,
            )
            for child in model.children or []
        ]
        return record

    @classmethod
    def _from_api_model(
        cls,
        model: CategoryObject | ChildCategoryObject,
        *,
        kind: CategoryKind,
        group_id: int | None,
    ) -> Self:
        """Create one normalized row from either generated category schema."""
        return cls(
            id=model.id,
            name=model.name,
            description=model.description,
            is_income=model.is_income,
            exclude_from_budget=model.exclude_from_budget,
            exclude_from_totals=model.exclude_from_totals,
            updated_at=model.updated_at,
            created_at=model.created_at,
            group_id=group_id,
            is_group=model.is_group,
            archived=model.archived,
            archived_at=model.archived_at,
            order=model.order,
            collapsed=model.collapsed,
            kind=kind,
        )

    def to_api(self) -> CategoryObject | ChildCategoryObject:
        """Reconstruct the generated category schema selected by ``kind``.

        Returns
        -------
        CategoryObject | ChildCategoryObject
            Generated parent or child category with values from this row.
        """
        if CategoryKind(self.kind) is CategoryKind.CHILD:
            return self.to_child_api()

        values = self._api_values()
        if self.children:
            values["children"] = [child.to_child_api() for child in self.children]
        elif self.is_group:
            values["children"] = []
        else:
            values["children"] = None
        return CategoryObject.model_validate(values)

    def to_child_api(self) -> ChildCategoryObject:
        """Reconstruct a generated child category object from this row.

        Returns
        -------
        ChildCategoryObject
            Generated child object containing every scalar category value.
        """
        return ChildCategoryObject.model_validate(self._api_values())

    def _api_values(self) -> dict[str, Any]:
        """Return all scalar values shared by both generated category schemas."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_income": self.is_income,
            "exclude_from_budget": self.exclude_from_budget,
            "exclude_from_totals": self.exclude_from_totals,
            "updated_at": self.updated_at,
            "created_at": self.created_at,
            "group_id": self.group_id,
            "is_group": self.is_group,
            "archived": self.archived,
            "archived_at": self.archived_at,
            "order": self.order,
            "collapsed": self.collapsed,
        }
