"""SQLModel record for the Lunch Money user."""

from typing import ClassVar, Self

from lunchmoney.models import CurrencyEnum, UserObject
from sqlalchemy import String
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """Persist every scalar field from a generated user object."""

    __tablename__: ClassVar[str] = "users"

    id: int = Field(primary_key=True, index=True)
    """Lunch Money user identifier."""
    name: str
    """User display name."""
    email: str
    """User email address."""
    account_id: int
    """Identifier of the linked budgeting account."""
    budget_name: str
    """Name of the linked budgeting account."""
    primary_currency: str = Field(sa_type=String)
    """String value of the user's generated currency enum."""
    api_key_label: str | None
    """Optional label assigned to the API key."""

    @classmethod
    def from_api(cls, model: UserObject) -> Self:
        """Create a database user from a generated API object.

        Parameters
        ----------
        model
            Generated Lunch Money user object to convert.

        Returns
        -------
        Self
            Database record containing every generated scalar field.
        """
        return cls(
            id=model.id,
            name=model.name,
            email=model.email,
            account_id=model.account_id,
            budget_name=model.budget_name,
            primary_currency=model.primary_currency.value,
            api_key_label=model.api_key_label,
        )

    def to_api(self) -> UserObject:
        """Reconstruct the generated user API object.

        Returns
        -------
        UserObject
            Generated object with values from this database record.
        """
        return UserObject.model_validate(
            {
                "id": self.id,
                "name": self.name,
                "email": self.email,
                "account_id": self.account_id,
                "budget_name": self.budget_name,
                "primary_currency": CurrencyEnum(self.primary_currency),
                "api_key_label": self.api_key_label,
            }
        )
