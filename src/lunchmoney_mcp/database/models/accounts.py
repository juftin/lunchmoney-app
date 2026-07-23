"""SQLModel records for linked and manually managed accounts."""

from builtins import type as builtin_type
from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar, Self, cast

from lunchmoney.models import (
    AccountTypeEnum,
    ManualAccountObject,
    PlaidAccountObject,
)
from sqlalchemy import JSON, Numeric, String
from sqlmodel import Field, SQLModel

from lunchmoney_mcp.database.models._datetime import (
    UTCDateTime,
    datetime_offset_minutes,
    restore_datetime_shape,
)


def _decimal_to_api_string(value: Decimal) -> str:
    """Format a stored decimal using Lunch Money's canonical four decimals."""
    return format(value, ".4f")


class PlaidAccount(SQLModel, table=True):
    """Persist every scalar field from a generated Plaid account object."""

    __tablename__: ClassVar[str] = "plaid_accounts"

    id: int = Field(primary_key=True, index=True)
    """Lunch Money Plaid account identifier."""
    plaid_item_id: str | None
    """Optional identifier of the owning Plaid connection."""
    date_linked: date
    """Date the account was first linked."""
    linked_by_name: str
    """Name of the user who linked the account."""
    name: str
    """Plaid-provided account name."""
    display_name: str | None
    """Optional user-facing account name."""
    type: str
    """Plaid primary account type."""
    subtype: str
    """Plaid account subtype."""
    mask: str
    """Masked account number suffix."""
    institution_name: str
    """Name of the account's financial institution."""
    status: str
    """Lunch Money account synchronization status."""
    allow_transaction_modifications: bool
    """Whether imported transactions may be modified."""
    limit: Decimal | None = Field(sa_type=cast(builtin_type[Any], Numeric(20, 10)))
    """Optional account credit limit."""
    balance: Decimal = Field(sa_type=cast(builtin_type[Any], Numeric(20, 10)))
    """Current account balance."""
    currency: str
    """Three-letter account currency code."""
    to_base: Decimal = Field(sa_type=cast(builtin_type[Any], Numeric(20, 10)))
    """Balance converted to the user's primary currency."""
    balance_last_update: datetime | None = Field(
        sa_type=cast(builtin_type[Any], UTCDateTime())
    )
    """Optional timestamp of the last balance update."""
    balance_last_update_offset_minutes: int | None = None
    """Source balance-update offset, or ``None`` when it was naive."""
    import_start_date: date | None
    """Optional earliest transaction import date."""
    last_import: datetime | None = Field(sa_type=cast(builtin_type[Any], UTCDateTime()))
    """Optional timestamp of the last transaction import."""
    last_import_offset_minutes: int | None = None
    """Source last-import offset, or ``None`` when it was naive."""
    last_fetch: datetime | None = Field(sa_type=cast(builtin_type[Any], UTCDateTime()))
    """Optional timestamp of the last successful Plaid fetch."""
    last_fetch_offset_minutes: int | None = None
    """Source last-fetch offset, or ``None`` when it was naive."""
    plaid_last_successful_update: datetime | None = Field(
        sa_type=cast(builtin_type[Any], UTCDateTime())
    )
    """Optional timestamp of Plaid's last successful institution update."""
    plaid_last_successful_update_offset_minutes: int | None = None
    """Source Plaid-success offset, or ``None`` when it was naive."""

    @classmethod
    def from_api(cls, model: PlaidAccountObject) -> Self:
        """Create a database account from a generated Plaid account.

        Parameters
        ----------
        model
            Generated Lunch Money Plaid account object to convert.

        Returns
        -------
        Self
            Database record containing every generated scalar field.
        """
        return cls(
            id=model.id,
            plaid_item_id=model.plaid_item_id,
            date_linked=model.date_linked,
            linked_by_name=model.linked_by_name,
            name=model.name,
            display_name=model.display_name,
            type=model.type,
            subtype=model.subtype,
            mask=model.mask,
            institution_name=model.institution_name,
            status=model.status,
            allow_transaction_modifications=model.allow_transaction_modifications,
            limit=Decimal(str(model.limit)) if model.limit is not None else None,
            balance=Decimal(model.balance),
            currency=model.currency,
            to_base=Decimal(str(model.to_base)),
            balance_last_update=model.balance_last_update,
            balance_last_update_offset_minutes=datetime_offset_minutes(
                model.balance_last_update
            ),
            import_start_date=model.import_start_date,
            last_import=model.last_import,
            last_import_offset_minutes=datetime_offset_minutes(model.last_import),
            last_fetch=model.last_fetch,
            last_fetch_offset_minutes=datetime_offset_minutes(model.last_fetch),
            plaid_last_successful_update=model.plaid_last_successful_update,
            plaid_last_successful_update_offset_minutes=datetime_offset_minutes(
                model.plaid_last_successful_update
            ),
        )

    def to_api(self) -> PlaidAccountObject:
        """Reconstruct the generated Plaid account API object.

        Returns
        -------
        PlaidAccountObject
            Generated object with values from this database record.
        """
        return PlaidAccountObject.model_validate(
            {
                "id": self.id,
                "plaid_item_id": self.plaid_item_id,
                "date_linked": self.date_linked,
                "linked_by_name": self.linked_by_name,
                "name": self.name,
                "display_name": self.display_name,
                "type": self.type,
                "subtype": self.subtype,
                "mask": self.mask,
                "institution_name": self.institution_name,
                "status": self.status,
                "allow_transaction_modifications": (
                    self.allow_transaction_modifications
                ),
                "limit": float(self.limit) if self.limit is not None else None,
                "balance": _decimal_to_api_string(self.balance),
                "currency": self.currency,
                "to_base": float(self.to_base),
                "balance_last_update": restore_datetime_shape(
                    self.balance_last_update,
                    offset_minutes=self.balance_last_update_offset_minutes,
                ),
                "import_start_date": self.import_start_date,
                "last_import": restore_datetime_shape(
                    self.last_import,
                    offset_minutes=self.last_import_offset_minutes,
                ),
                "last_fetch": restore_datetime_shape(
                    self.last_fetch,
                    offset_minutes=self.last_fetch_offset_minutes,
                ),
                "plaid_last_successful_update": restore_datetime_shape(
                    self.plaid_last_successful_update,
                    offset_minutes=self.plaid_last_successful_update_offset_minutes,
                ),
            }
        )


class ManualAccount(SQLModel, table=True):
    """Persist every scalar field from a generated manual account object."""

    __tablename__: ClassVar[str] = "manual_accounts"

    id: int = Field(primary_key=True, index=True)
    """Lunch Money manual account identifier."""
    name: str
    """User-defined account name."""
    institution_name: str | None
    """Optional name of the account's financial institution."""
    display_name: str | None
    """Optional user-facing account name."""
    type: str = Field(sa_type=String)
    """String value of the generated account-type enum."""
    subtype: str | None
    """Optional manual account subtype."""
    balance: Decimal = Field(sa_type=cast(builtin_type[Any], Numeric(20, 10)))
    """Current account balance."""
    currency: str
    """Three-letter account currency code."""
    to_base: Decimal = Field(sa_type=cast(builtin_type[Any], Numeric(20, 10)))
    """Balance converted to the user's primary currency."""
    balance_as_of: datetime = Field(sa_type=cast(builtin_type[Any], UTCDateTime()))
    """Timestamp at which the balance was current."""
    balance_as_of_offset_minutes: int | None = None
    """Source balance timestamp offset, or ``None`` when it was naive."""
    status: str
    """Manual account lifecycle status."""
    closed_on: date | None
    """Optional date the account was closed."""
    external_id: str | None
    """Optional caller-defined account identifier."""
    custom_metadata: dict[str, Any] | None = Field(default=None, sa_type=JSON)
    """Optional arbitrary user-defined JSON metadata."""
    exclude_from_transactions: bool
    """Whether the account is excluded from transaction assignment."""
    created_by_name: str
    """Name of the user who created the account."""
    created_at: datetime = Field(sa_type=cast(builtin_type[Any], UTCDateTime()))
    """Timestamp when the account was created."""
    created_at_offset_minutes: int | None = None
    """Source creation timestamp offset, or ``None`` when it was naive."""
    updated_at: datetime = Field(sa_type=cast(builtin_type[Any], UTCDateTime()))
    """Timestamp when the account was last updated."""
    updated_at_offset_minutes: int | None = None
    """Source update timestamp offset, or ``None`` when it was naive."""

    @classmethod
    def from_api(cls, model: ManualAccountObject) -> Self:
        """Create a database account from a generated manual account.

        Parameters
        ----------
        model
            Generated Lunch Money manual account object to convert.

        Returns
        -------
        Self
            Database record containing every generated scalar field.
        """
        return cls(
            id=model.id,
            name=model.name,
            institution_name=model.institution_name,
            display_name=model.display_name,
            type=model.type.value,
            subtype=model.subtype,
            balance=Decimal(model.balance),
            currency=model.currency,
            to_base=Decimal(str(model.to_base)),
            balance_as_of=model.balance_as_of,
            balance_as_of_offset_minutes=datetime_offset_minutes(model.balance_as_of),
            status=model.status,
            closed_on=model.closed_on,
            external_id=model.external_id,
            custom_metadata=model.custom_metadata,
            exclude_from_transactions=model.exclude_from_transactions,
            created_by_name=model.created_by_name,
            created_at=model.created_at,
            created_at_offset_minutes=datetime_offset_minutes(model.created_at),
            updated_at=model.updated_at,
            updated_at_offset_minutes=datetime_offset_minutes(model.updated_at),
        )

    def to_api(self) -> ManualAccountObject:
        """Reconstruct the generated manual account API object.

        Returns
        -------
        ManualAccountObject
            Generated object with values from this database record.
        """
        return ManualAccountObject.model_validate(
            {
                "id": self.id,
                "name": self.name,
                "institution_name": self.institution_name,
                "display_name": self.display_name,
                "type": AccountTypeEnum(self.type),
                "subtype": self.subtype,
                "balance": _decimal_to_api_string(self.balance),
                "currency": self.currency,
                "to_base": float(self.to_base),
                "balance_as_of": restore_datetime_shape(
                    self.balance_as_of,
                    offset_minutes=self.balance_as_of_offset_minutes,
                ),
                "status": self.status,
                "closed_on": self.closed_on,
                "external_id": self.external_id,
                "custom_metadata": self.custom_metadata,
                "exclude_from_transactions": self.exclude_from_transactions,
                "created_by_name": self.created_by_name,
                "created_at": restore_datetime_shape(
                    self.created_at,
                    offset_minutes=self.created_at_offset_minutes,
                ),
                "updated_at": restore_datetime_shape(
                    self.updated_at,
                    offset_minutes=self.updated_at_offset_minutes,
                ),
            }
        )
