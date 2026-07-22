"""Deterministic synthetic generated-model factories for database tests."""

from datetime import UTC, date, datetime

from lunchmoney.models import (
    AccountTypeEnum,
    CurrencyEnum,
    ManualAccountObject,
    PlaidAccountObject,
    TagObject,
    UserObject,
)

SYNTHETIC_DATE = date(2026, 1, 1)
"""Stable calendar date used by generated-model fixtures."""
SYNTHETIC_DATETIME = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
"""Stable UTC timestamp used by generated-model fixtures."""


def user_object() -> UserObject:
    """Build a complete synthetic generated user object."""
    return UserObject.model_validate(
        {
            "name": "Synthetic User",
            "email": "synthetic-user@example.invalid",
            "id": 1,
            "account_id": 100,
            "budget_name": "Synthetic Budget",
            "primary_currency": next(iter(CurrencyEnum)),
            "api_key_label": "Synthetic API Key Label",
        }
    )


def plaid_account_object() -> PlaidAccountObject:
    """Build a complete synthetic generated Plaid account object."""
    return PlaidAccountObject.model_validate(
        {
            "id": 2,
            "plaid_item_id": "synthetic-plaid-item",
            "date_linked": SYNTHETIC_DATE,
            "linked_by_name": "Synthetic User",
            "name": "Synthetic Plaid Account",
            "display_name": "Synthetic Checking",
            "type": "depository",
            "subtype": "checking",
            "mask": "0000",
            "institution_name": "Synthetic Bank",
            "status": "active",
            "allow_transaction_modifications": True,
            "limit": 5000.25,
            "balance": "1250.5",
            "currency": next(iter(CurrencyEnum)).value,
            "to_base": 1250.5,
            "balance_last_update": SYNTHETIC_DATETIME,
            "import_start_date": SYNTHETIC_DATE,
            "last_import": SYNTHETIC_DATETIME,
            "last_fetch": SYNTHETIC_DATETIME,
            "plaid_last_successful_update": SYNTHETIC_DATETIME,
        }
    )


def manual_account_object() -> ManualAccountObject:
    """Build a complete synthetic generated manual account object."""
    return ManualAccountObject.model_validate(
        {
            "id": 3,
            "name": "Synthetic Manual Account",
            "institution_name": "Synthetic Credit Union",
            "display_name": "Synthetic Savings",
            "type": next(iter(AccountTypeEnum)),
            "subtype": "savings",
            "balance": "750.25",
            "currency": next(iter(CurrencyEnum)).value,
            "to_base": 750.25,
            "balance_as_of": SYNTHETIC_DATETIME,
            "status": "active",
            "closed_on": SYNTHETIC_DATE,
            "external_id": "synthetic-external-account",
            "custom_metadata": {
                "source": "synthetic-fixture",
                "nested": {"version": 1},
            },
            "exclude_from_transactions": False,
            "created_by_name": "Synthetic User",
            "created_at": SYNTHETIC_DATETIME,
            "updated_at": SYNTHETIC_DATETIME,
        }
    )


def tag_object(tag_id: int = 1) -> TagObject:
    """Build a complete synthetic generated tag object."""
    return TagObject.model_validate(
        {
            "id": tag_id,
            "name": f"Synthetic Tag {tag_id}",
            "description": "Synthetic tag used by database tests",
            "text_color": "#ffffff",
            "background_color": "#000000",
            "updated_at": SYNTHETIC_DATETIME,
            "created_at": SYNTHETIC_DATETIME,
            "archived": True,
            "archived_at": SYNTHETIC_DATETIME,
        }
    )
