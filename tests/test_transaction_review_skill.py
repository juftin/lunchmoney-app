"""Unit tests for the lunchmoney-transaction-review skill helper engine."""

from __future__ import annotations

import json
from pathlib import Path
from runpy import run_path
from typing import Any

ROOT = Path(__file__).parents[1]
"""Repository root directory."""

SKILL_SCRIPT = (
    ROOT / ".agents/skills/lunchmoney-transaction-review/scripts/process_review.py"
)
"""Path to the skill processing script."""


def _load_engine() -> dict[str, Any]:
    """Load the process_review helper script as a module."""
    return run_path(str(SKILL_SCRIPT))


def test_clean_universal_payee_normalizes_merchant_names() -> None:
    """Ensure processor prefixes and URLs are stripped while true merchants are preserved."""
    engine = _load_engine()
    clean_payee = engine["clean_universal_payee"]

    # Preserves clean mixed-case payee
    assert (
        clean_payee("Cerebral Brewing", "TST*WEST HIGHLAND", None) == "Cerebral Brewing"
    )

    # Strips processor prefix from ALL-CAPS string
    assert (
        clean_payee("TST* DENVER BEER CO. - SO", "TST* DENVER BEER CO. - SO", None)
        == "Denver Beer Co."
    )

    # Uses high-confidence merchant counterparty over payment terminal
    meta = {
        "counterparties": [
            {
                "confidence_level": "VERY_HIGH",
                "name": "Toast",
                "type": "payment_terminal",
            },
            {"confidence_level": "LOW", "name": "Right Cream", "type": "merchant"},
        ],
        "merchant_name": "Right Cream",
    }
    assert clean_payee("RIGHT CREAM", "RIGHT CREAM", meta) == "Right Cream"

    # Cleans URL extensions and Amazon tip strings
    assert clean_payee("APPLE.COM/US", "APPLE.COM/US", None) == "Apple"
    assert (
        clean_payee("Amazon Tips*5Q96K1GS2", "Amazon Tips*5Q96K1GS2", None)
        == "Whole Foods"
    )


def test_category_matcher_prefers_child_categories() -> None:
    """Ensure classification prioritizes specific child/leaf categories over parent groups."""
    engine = _load_engine()
    matcher_cls = engine["CategoryMatcher"]

    categories = [
        {"id": 1, "name": "Dining", "is_group": True, "group_id": None},
        {"id": 10, "name": "Restaurants", "is_group": False, "group_id": 1},
        {"id": 11, "name": "Takeout", "is_group": False, "group_id": 1},
        {"id": 2, "name": "Income", "is_group": True, "group_id": None},
        {"id": 20, "name": "Salary", "is_group": False, "group_id": 2},
        {"id": 3, "name": "Groceries", "is_group": False, "group_id": None},
        {"id": 4, "name": "Payment, Transfer", "is_group": False, "group_id": None},
    ]

    matcher = matcher_cls(categories)

    # Fast food matches Takeout child category
    tx_takeout = {
        "original_name": "CHIPOTLE 123",
        "payee": "Chipotle",
        "amount": "15.00",
        "plaid_metadata": {
            "personal_finance_category": {
                "detailed": "FOOD_AND_DRINK_FAST_FOOD",
                "primary": "FOOD_AND_DRINK",
            }
        },
    }
    cid, cname, _ = matcher.match(tx_takeout)
    assert cid == 11
    assert cname == "Takeout"

    # Payroll matches Salary child category under Income
    tx_salary = {
        "original_name": "ACME PAYROLL",
        "payee": "Acme Corp",
        "amount": "-5000.00",
        "plaid_metadata": {
            "personal_finance_category": {
                "detailed": "INCOME_WAGES",
                "primary": "INCOME",
            }
        },
    }
    cid, cname, note = matcher.match(tx_salary)
    assert cid == 20
    assert cname == "Salary"
    assert note == "Salary"

    # Credit card payment matches Payment, Transfer
    tx_payment = {
        "original_name": "PAYMENT THANK YOU-MOBILE",
        "payee": "Chase",
        "amount": "-500.00",
        "plaid_metadata": {
            "personal_finance_category": {
                "detailed": "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT",
                "primary": "LOAN_PAYMENTS",
            }
        },
    }
    cid, cname, _ = matcher.match(tx_payment)
    assert cid == 4
    assert cname == "Payment, Transfer"


def test_find_actual_recurring_matches_filters_unrelated_categories() -> None:
    """Verify recurring item matcher rejects credit card payments matching mortgages."""
    engine = _load_engine()
    matcher = engine["find_actual_recurring_matches"]

    actual_recurring = [
        {
            "id": 100,
            "status": "reviewed",
            "transaction_criteria": {
                "amount": "2645.9600",
                "payee": "Chase",
                "category_id": 380600,
            },
            "overrides": {},
        },
        {
            "id": 200,
            "status": "reviewed",
            "transaction_criteria": {
                "amount": "268.9400",
                "payee": "Department of Education",
                "category_id": 380602,
            },
            "overrides": {},
        },
    ]

    # Department of education exact match
    tx_edu = {"amount": "268.9400", "original_name": "DEPT EDUCATION STUDENT LN"}
    matches = matcher(tx_edu, "Department of Education", actual_recurring)
    assert len(matches) == 1
    assert matches[0][0]["id"] == 200

    # Chase credit card payment should NOT match Chase mortgage recurring item
    tx_chase_payment = {"amount": "667.8500", "original_name": "CHASE CREDIT CRD EPAY"}
    matches = matcher(tx_chase_payment, "Chase", actual_recurring)
    assert len(matches) == 0


def test_process_review_data_generates_valid_payload(tmp_path: Path) -> None:
    """Ensure process_review_data outputs a complete, well-formed bulk update payload."""
    engine = _load_engine()
    process_review_data = engine["process_review_data"]

    sample_data = {
        "transactions": [
            {
                "transaction": {
                    "id": 9991,
                    "date": "2026-08-28",
                    "amount": "38.24",
                    "payee": "Mendocino Farms",
                    "original_name": "MENDOCINOFARMS",
                    "plaid_metadata": {
                        "personal_finance_category": {
                            "detailed": "FOOD_AND_DRINK_FAST_FOOD",
                            "primary": "FOOD_AND_DRINK",
                        }
                    },
                },
                "category": None,
                "plaid_account": {"display_name": "Chase - Sapphire"},
            }
        ],
        "categories": [
            {"id": 1, "name": "Dining", "is_group": True},
            {"id": 11, "name": "Takeout", "is_group": False, "group_id": 1},
        ],
        "accounts": {"plaid_accounts": []},
    }

    output_path = tmp_path / "updates.json"
    updates = process_review_data(sample_data, output_updates_path=output_path)

    assert len(updates) == 1
    assert updates[0]["id"] == 9991
    assert updates[0]["payee"] == "Mendocino Farms"
    assert updates[0]["category_id"] == 11
    assert updates[0]["status"] == "reviewed"

    saved_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved_payload["transactions"][0]["id"] == 9991
