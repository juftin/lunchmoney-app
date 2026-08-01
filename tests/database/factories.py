"""Deterministic synthetic generated-model factories for database tests."""

from datetime import date, datetime, timezone

from lunchmoney.models import (
    AccountTypeEnum,
    CategoryObject,
    ChildCategoryObject,
    ChildTransactionObject,
    CurrencyEnum,
    ManualAccountObject,
    PlaidAccountObject,
    TagObject,
    TransactionAttachmentObject,
    TransactionObject,
    UserObject,
)

UTC = timezone.utc
# Canonical UTC timezone compatible with all supported Python versions.

SYNTHETIC_DATE = date(2026, 1, 1)
# Stable calendar date used by generated-model fixtures.
SYNTHETIC_DATETIME = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
# Stable UTC timestamp used by generated-model fixtures.


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
            "balance": "1250.5000",
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
            "balance": "750.2500",
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


def child_category_object() -> ChildCategoryObject:
    """Build a complete synthetic generated child category object."""
    return ChildCategoryObject.model_validate(
        {
            "id": 11,
            "name": "Synthetic Child Category",
            "description": "Synthetic child category used by database tests",
            "is_income": False,
            "exclude_from_budget": False,
            "exclude_from_totals": True,
            "updated_at": SYNTHETIC_DATETIME,
            "created_at": SYNTHETIC_DATETIME,
            "group_id": 10,
            "is_group": False,
            "archived": True,
            "archived_at": SYNTHETIC_DATETIME,
            "order": 2,
            "collapsed": False,
        }
    )


def category_object(
    children: list[ChildCategoryObject] | None = None,
) -> CategoryObject:
    """Build a complete synthetic generated parent category object."""
    return CategoryObject.model_validate(
        {
            "id": 10,
            "name": "Synthetic Category",
            "description": "Synthetic category used by database tests",
            "is_income": False,
            "exclude_from_budget": True,
            "exclude_from_totals": False,
            "updated_at": SYNTHETIC_DATETIME,
            "created_at": SYNTHETIC_DATETIME,
            "group_id": None,
            "is_group": children is not None,
            "children": children,
            "archived": False,
            "archived_at": None,
            "order": 1,
            "collapsed": True,
        }
    )


def transaction_attachment_object(
    attachment_id: int | None = 501,
) -> TransactionAttachmentObject:
    """Build a complete synthetic generated transaction attachment object."""
    return TransactionAttachmentObject.model_validate(
        {
            "id": attachment_id,
            "uploaded_by": 1,
            "name": f"synthetic-attachment-{attachment_id}.pdf",
            "type": "application/pdf",
            "size": 128,
            "notes": "Synthetic attachment used by database tests",
            "created_at": SYNTHETIC_DATETIME,
        }
    )


def child_transaction_object(
    *,
    transaction_id: int = 101,
    split_parent_id: int | None = 100,
    group_parent_id: int | None = None,
    tag_ids: list[int] | None = None,
    files: list[TransactionAttachmentObject] | None = None,
) -> ChildTransactionObject:
    """Build a complete synthetic generated child transaction object."""
    return ChildTransactionObject.model_validate(
        {
            "id": transaction_id,
            "date": SYNTHETIC_DATE,
            "amount": "25.1250",
            "currency": next(iter(CurrencyEnum)),
            "to_base": 25.125,
            "recurring_id": 701,
            "payee": "Synthetic Child Payee",
            "original_name": "SYNTHETIC CHILD PAYEE RAW",
            "category_id": 10,
            "notes": "Synthetic child transaction notes",
            "status": "reviewed",
            "is_pending": False,
            "created_at": SYNTHETIC_DATETIME,
            "updated_at": SYNTHETIC_DATETIME,
            "is_split_parent": False,
            "split_parent_id": split_parent_id,
            "is_group_parent": False,
            "group_parent_id": group_parent_id,
            "manual_account_id": 3,
            "plaid_account_id": None,
            "tag_ids": tag_ids if tag_ids is not None else [22],
            "source": "split",
            "external_id": "synthetic-child-external-id",
            "plaid_metadata": {"merchant": {"name": "Synthetic Child Merchant"}},
            "custom_metadata": {
                "source": "synthetic-child-fixture",
                "nested": {"version": 1},
            },
            "files": files,
        }
    )


def transaction_object(
    *,
    transaction_id: int = 100,
    tag_ids: list[int] | None = None,
    children: list[ChildTransactionObject] | None = None,
    files: list[TransactionAttachmentObject] | None = None,
    is_split_parent: bool | None = True,
    is_group_parent: bool = False,
) -> TransactionObject:
    """Build a complete synthetic generated parent transaction object."""
    return TransactionObject.model_validate(
        {
            "id": transaction_id,
            "date": SYNTHETIC_DATE,
            "amount": "125.6250",
            "currency": next(iter(CurrencyEnum)),
            "to_base": 125.625,
            "recurring_id": 700,
            "payee": "Synthetic Parent Payee",
            "original_name": "SYNTHETIC PARENT PAYEE RAW",
            "category_id": 10,
            "plaid_account_id": 2,
            "manual_account_id": None,
            "external_id": "synthetic-parent-external-id",
            "tag_ids": tag_ids if tag_ids is not None else [21],
            "notes": "Synthetic parent transaction notes",
            "status": "reviewed",
            "is_pending": False,
            "created_at": SYNTHETIC_DATETIME,
            "updated_at": SYNTHETIC_DATETIME,
            "is_split_parent": is_split_parent,
            "split_parent_id": None,
            "is_group_parent": is_group_parent,
            "group_parent_id": None,
            "children": children,
            "plaid_metadata": {"merchant": {"name": "Synthetic Merchant"}},
            "custom_metadata": {
                "source": "synthetic-parent-fixture",
                "nested": {"version": 1},
            },
            "files": files,
            "source": "plaid",
        }
    )
