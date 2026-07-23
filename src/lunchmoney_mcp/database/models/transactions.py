"""Normalized SQLModel records for Lunch Money transaction graphs."""

from builtins import type as builtin_type
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, ClassVar, Optional, Self, cast

from lunchmoney.models import (
    ChildTransactionObject,
    TransactionAttachmentObject,
    TransactionObject,
)
from sqlalchemy import JSON, Numeric, String
from sqlmodel import Field, Relationship, SQLModel

from lunchmoney_mcp.database.models._datetime import (
    UTCDateTime,
    datetime_offset_minutes,
    restore_datetime_shape,
)
from lunchmoney_mcp.database.models.accounts import ManualAccount, PlaidAccount
from lunchmoney_mcp.database.models.categories import Category
from lunchmoney_mcp.database.models.tags import Tag


def _decimal_to_api_string(value: Decimal) -> str:
    """Format a stored transaction amount using the API's four decimals."""
    return format(value, ".4f")


class TransactionKind(StrEnum):
    """Identify which generated transaction schema a row represents."""

    PARENT = "parent"
    """A top-level generated transaction object."""
    CHILD = "child"
    """A generated child transaction nested beneath a parent."""


class TransactionTagLink(SQLModel, table=True):
    """Associate one normalized transaction with one normalized tag."""

    __tablename__: ClassVar[str] = "transaction_tag_links"

    transaction_id: int = Field(
        foreign_key="transactions.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    """Identifier of the associated transaction."""
    tag_id: int = Field(
        foreign_key="tags.id",
        ondelete="RESTRICT",
        primary_key=True,
    )
    """Identifier of the associated tag."""
    position: int
    """Zero-based position of the tag in the source API list."""

    transaction: Optional["Transaction"] = Relationship(back_populates="tag_links")
    """Transaction that owns this association row."""
    tag: Optional[Tag] = Relationship()
    """Tag referenced by this association row."""


class TransactionAttachment(SQLModel, table=True):
    """Persist one attachment owned by a normalized transaction."""

    __tablename__: ClassVar[str] = "transaction_attachments"

    id: int | None = Field(default=None, primary_key=True)
    """Generated internal key used when the API attachment has no identifier."""
    api_id: int | None = Field(default=None, index=True)
    """Optional attachment identifier supplied by Lunch Money."""
    transaction_id: int = Field(
        foreign_key="transactions.id",
        ondelete="CASCADE",
    )
    """Identifier of the transaction that owns the attachment."""
    position: int
    """Zero-based position of the attachment in the source API list."""
    uploaded_by: int | None = None
    """Optional identifier of the user who uploaded the attachment."""
    name: str | None = None
    """Optional attachment file name."""
    type: str | None = None
    """Optional attachment MIME type."""
    size: int | None = None
    """Optional attachment size in kilobytes."""
    notes: str | None = None
    """Optional notes stored with the attachment."""
    created_at: datetime | None = Field(
        default=None,
        sa_type=cast(builtin_type[Any], UTCDateTime()),
    )
    """Optional timestamp when the attachment was created."""
    created_at_offset_minutes: int | None = None
    """Source UTC offset in minutes, or ``None`` when the source was naive."""

    transaction: Optional["Transaction"] = Relationship(back_populates="attachments")
    """Transaction that owns this attachment."""

    @classmethod
    def from_api(
        cls,
        model: TransactionAttachmentObject,
        *,
        transaction_id: int,
        position: int,
    ) -> Self:
        """Create an owned attachment from a generated API object.

        Parameters
        ----------
        model
            Generated Lunch Money attachment to convert.
        transaction_id
            Identifier of the transaction that owns the attachment.
        position
            Zero-based position of the attachment in the source API list.

        Returns
        -------
        Self
            Attachment row with a generated internal key and retained API ID.
        """
        return cls(
            api_id=model.id,
            transaction_id=transaction_id,
            position=position,
            uploaded_by=model.uploaded_by,
            name=model.name,
            type=model.type,
            size=model.size,
            notes=model.notes,
            created_at=model.created_at,
            created_at_offset_minutes=datetime_offset_minutes(model.created_at),
        )

    def to_api(self) -> TransactionAttachmentObject:
        """Reconstruct the generated Lunch Money attachment object.

        Returns
        -------
        TransactionAttachmentObject
            Generated object containing every API attachment value.
        """
        return TransactionAttachmentObject.model_validate(
            {
                "id": self.api_id,
                "uploaded_by": self.uploaded_by,
                "name": self.name,
                "type": self.type,
                "size": self.size,
                "notes": self.notes,
                "created_at": restore_datetime_shape(
                    self.created_at,
                    offset_minutes=self.created_at_offset_minutes,
                ),
            }
        )


class Transaction(SQLModel, table=True):
    """Persist parent and child transactions as a normalized owned graph."""

    __tablename__: ClassVar[str] = "transactions"

    id: int = Field(primary_key=True, index=True)
    """Lunch Money transaction identifier."""
    var_date: date
    """Calendar date on which the transaction occurred."""
    amount: Decimal = Field(sa_type=cast(builtin_type[Any], Numeric(20, 10)))
    """Transaction amount in its original currency."""
    currency: str = Field(sa_type=String)
    """Three-letter transaction currency code."""
    to_base: Decimal = Field(sa_type=cast(builtin_type[Any], Numeric(20, 10)))
    """Transaction amount converted to the budget's primary currency."""
    recurring_id: int | None
    """Optional identifier of the matched recurring item."""
    payee: str
    """Displayed transaction payee."""
    original_name: str | None = None
    """Optional original payee name from the transaction source."""
    category_id: int | None = Field(
        foreign_key="categories.id",
        ondelete="RESTRICT",
    )
    """Optional identifier of the transaction's category."""
    plaid_account_id: int | None = Field(
        foreign_key="plaid_accounts.id",
        ondelete="RESTRICT",
    )
    """Optional identifier of the transaction's synced account."""
    manual_account_id: int | None = Field(
        foreign_key="manual_accounts.id",
        ondelete="RESTRICT",
    )
    """Optional identifier of the transaction's manual account."""
    external_id: str | None
    """Optional caller-defined transaction identifier."""
    notes: str | None
    """Optional transaction notes."""
    status: str
    """Transaction review status."""
    is_pending: bool
    """Whether the source account considers the transaction pending."""
    created_at: datetime = Field(sa_type=cast(builtin_type[Any], UTCDateTime()))
    """Timestamp when the transaction was created."""
    created_at_offset_minutes: int | None = None
    """Created timestamp's source offset, or ``None`` when it was naive."""
    updated_at: datetime = Field(sa_type=cast(builtin_type[Any], UTCDateTime()))
    """Timestamp when the transaction was last updated."""
    updated_at_offset_minutes: int | None = None
    """Updated timestamp's source offset, or ``None`` when it was naive."""
    is_split_parent: bool | None = None
    """Whether this row owns split child transactions."""
    split_parent_id: int | None = Field(
        foreign_key="transactions.id",
        ondelete="CASCADE",
    )
    """Optional identifier of the original transaction before a split."""
    is_group_parent: bool
    """Whether this row owns grouped child transactions."""
    group_parent_id: int | None = Field(
        foreign_key="transactions.id",
        ondelete="CASCADE",
    )
    """Optional identifier of the group transaction containing this row."""
    plaid_metadata: dict[str, Any] | None = Field(default=None, sa_type=JSON)
    """Optional arbitrary metadata received from Plaid."""
    custom_metadata: dict[str, Any] | None = Field(default=None, sa_type=JSON)
    """Optional arbitrary metadata supplied by an API caller."""
    source: str | None
    """Optional source that created the transaction."""
    child_position: int | None = None
    """Global position within the source parent's nested child list."""
    children_present: bool
    """Whether the source parent explicitly included its children list."""
    files_present: bool
    """Whether the source schema explicitly included its attachment list."""
    kind: TransactionKind = Field(sa_type=String)
    """Generated transaction schema represented by this normalized row."""

    category: Optional[Category] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "Transaction.category_id"}
    )
    """Category referenced by this transaction."""
    plaid_account: Optional[PlaidAccount] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "Transaction.plaid_account_id"}
    )
    """Synced account referenced by this transaction."""
    manual_account: Optional[ManualAccount] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "Transaction.manual_account_id"}
    )
    """Manual account referenced by this transaction."""
    split_parent: Optional["Transaction"] = Relationship(
        back_populates="split_children",
        sa_relationship_kwargs={
            "foreign_keys": "Transaction.split_parent_id",
            "remote_side": "Transaction.id",
        },
    )
    """Original transaction that owns this split child."""
    split_children: list["Transaction"] = Relationship(
        back_populates="split_parent",
        cascade_delete=True,
        sa_relationship_kwargs={
            "foreign_keys": "Transaction.split_parent_id",
            "order_by": "Transaction.child_position",
            "single_parent": True,
        },
    )
    """Child rows produced by splitting this transaction."""
    group_parent: Optional["Transaction"] = Relationship(
        back_populates="group_children",
        sa_relationship_kwargs={
            "foreign_keys": "Transaction.group_parent_id",
            "remote_side": "Transaction.id",
        },
    )
    """Group transaction that owns this grouped child."""
    group_children: list["Transaction"] = Relationship(
        back_populates="group_parent",
        cascade_delete=True,
        sa_relationship_kwargs={
            "foreign_keys": "Transaction.group_parent_id",
            "order_by": "Transaction.child_position",
            "single_parent": True,
        },
    )
    """Child rows grouped beneath this transaction."""
    tag_links: list[TransactionTagLink] = Relationship(
        back_populates="transaction",
        cascade_delete=True,
        sa_relationship_kwargs={
            "order_by": "TransactionTagLink.position",
            "single_parent": True,
        },
    )
    """Owned normalized association rows retaining every API tag ID."""
    tags: list[Tag] = Relationship(
        link_model=TransactionTagLink,
        sa_relationship_kwargs={
            "order_by": "TransactionTagLink.position",
            "viewonly": True,
        },
    )
    """Tags associated with this transaction through the normalized link table."""
    attachments: list[TransactionAttachment] = Relationship(
        back_populates="transaction",
        cascade_delete=True,
        sa_relationship_kwargs={
            "order_by": "TransactionAttachment.position",
            "single_parent": True,
        },
    )
    """Ordered attachment rows owned by this transaction."""

    @classmethod
    def from_api(
        cls,
        model: TransactionObject | ChildTransactionObject,
        *,
        tags: Iterable[Tag] = (),
    ) -> Self:
        """Create a normalized transaction graph from a generated API object.

        Parameters
        ----------
        model
            Generated parent or child Lunch Money transaction to convert.
        tags
            Available normalized tags referenced by the transaction graph.

        Returns
        -------
        Self
            Transaction row with normalized nested rows and associations.
        """
        available_tags = {tag.id: tag for tag in tags}
        kind = (
            TransactionKind.CHILD
            if isinstance(model, ChildTransactionObject)
            else TransactionKind.PARENT
        )
        record = cls._from_api_model(model, kind=kind)
        record._set_tag_graph(model.tag_ids, available_tags=available_tags)
        record.attachments = [
            TransactionAttachment.from_api(
                file,
                transaction_id=model.id,
                position=position,
            )
            for position, file in enumerate(model.files or [])
        ]

        if isinstance(model, TransactionObject):
            for position, child_model in enumerate(model.children or []):
                is_split_child = child_model.split_parent_id == model.id
                is_group_child = child_model.group_parent_id == model.id
                if is_split_child == is_group_child:
                    msg = (
                        f"Child transaction {child_model.id} must belong to exactly "
                        "one split or group relationship on parent transaction "
                        f"{model.id}"
                    )
                    raise ValueError(msg)
                child = cls.from_api(child_model, tags=available_tags.values())
                child.child_position = position
                if is_split_child:
                    record.split_children.append(child)
                else:
                    record.group_children.append(child)

        return record

    @classmethod
    def _from_api_model(
        cls,
        model: TransactionObject | ChildTransactionObject,
        *,
        kind: TransactionKind,
    ) -> Self:
        """Create one normalized row from either generated transaction schema."""
        return cls(
            id=model.id,
            var_date=model.var_date,
            amount=Decimal(model.amount),
            currency=model.currency.value,
            to_base=Decimal(str(model.to_base)),
            recurring_id=model.recurring_id,
            payee=model.payee,
            original_name=model.original_name,
            category_id=model.category_id,
            plaid_account_id=model.plaid_account_id,
            manual_account_id=model.manual_account_id,
            external_id=model.external_id,
            notes=model.notes,
            status=model.status,
            is_pending=model.is_pending,
            created_at=model.created_at,
            created_at_offset_minutes=datetime_offset_minutes(model.created_at),
            updated_at=model.updated_at,
            updated_at_offset_minutes=datetime_offset_minutes(model.updated_at),
            is_split_parent=model.is_split_parent,
            split_parent_id=model.split_parent_id,
            is_group_parent=model.is_group_parent,
            group_parent_id=model.group_parent_id,
            plaid_metadata=model.plaid_metadata,
            custom_metadata=model.custom_metadata,
            source=model.source,
            children_present=(
                isinstance(model, TransactionObject) and model.children is not None
            ),
            files_present=model.files is not None,
            kind=kind,
        )

    def _set_tag_graph(
        self,
        tag_ids: list[int],
        *,
        available_tags: dict[int, Tag],
    ) -> None:
        """Populate owned link rows and resolved native tag relationships."""
        self.tag_links = [
            TransactionTagLink(
                transaction_id=self.id,
                tag_id=tag_id,
                position=position,
                tag=available_tags.get(tag_id),
            )
            for position, tag_id in enumerate(tag_ids)
        ]
        self.tags = [
            available_tags[tag_id] for tag_id in tag_ids if tag_id in available_tags
        ]

    def to_api(self) -> TransactionObject | ChildTransactionObject:
        """Reconstruct the generated transaction schema selected by ``kind``.

        Returns
        -------
        TransactionObject | ChildTransactionObject
            Generated parent or child transaction containing the complete graph.
        """
        if TransactionKind(self.kind) is TransactionKind.CHILD:
            return self.to_child_api()

        values = self._api_values()
        values["children"] = (
            [child.to_child_api() for child in self._nested_children()]
            if self.children_present
            else None
        )
        return TransactionObject.model_validate(values)

    def to_child_api(self) -> ChildTransactionObject:
        """Reconstruct a generated child transaction from this normalized row.

        Returns
        -------
        ChildTransactionObject
            Generated child transaction containing all scalar and nested values.
        """
        return ChildTransactionObject.model_validate(self._api_values())

    def _nested_children(self) -> list["Transaction"]:
        """Return all owned nested transaction rows without duplicates."""
        children: list[Transaction] = []
        child_ids: set[int] = set()
        for child in [*self.split_children, *self.group_children]:
            if child.id not in child_ids:
                children.append(child)
                child_ids.add(child.id)
        return sorted(children, key=lambda child: child.child_position or 0)

    def _api_values(self) -> dict[str, Any]:
        """Return all API values shared by parent and child transaction schemas."""
        return {
            "id": self.id,
            "var_date": self.var_date,
            "amount": _decimal_to_api_string(self.amount),
            "currency": self.currency,
            "to_base": float(self.to_base),
            "recurring_id": self.recurring_id,
            "payee": self.payee,
            "original_name": self.original_name,
            "category_id": self.category_id,
            "plaid_account_id": self.plaid_account_id,
            "manual_account_id": self.manual_account_id,
            "external_id": self.external_id,
            "tag_ids": [link.tag_id for link in self.tag_links],
            "notes": self.notes,
            "status": self.status,
            "is_pending": self.is_pending,
            "created_at": restore_datetime_shape(
                self.created_at,
                offset_minutes=self.created_at_offset_minutes,
            ),
            "updated_at": restore_datetime_shape(
                self.updated_at,
                offset_minutes=self.updated_at_offset_minutes,
            ),
            "is_split_parent": self.is_split_parent,
            "split_parent_id": self.split_parent_id,
            "is_group_parent": self.is_group_parent,
            "group_parent_id": self.group_parent_id,
            "plaid_metadata": self.plaid_metadata,
            "custom_metadata": self.custom_metadata,
            "files": (
                [attachment.to_api() for attachment in self.attachments]
                if self.files_present
                else None
            ),
            "source": self.source,
        }
