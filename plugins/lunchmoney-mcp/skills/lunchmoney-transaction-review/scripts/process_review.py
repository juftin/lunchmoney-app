#!/usr/bin/env python3
"""
Universal Lunch Money Transaction Review Processor.

A zero-dependency, generalized engine that parses review_transactions payloads,
resolves clean payees from Plaid metadata, maps transactions to specific child
categories, scans actual recurring items, and generates ready-to-use bulk update payloads.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


def clean_universal_payee(
    current_payee: str | None, orig: str | None, meta: dict[str, Any] | None
) -> str:
    """Universally clean and normalize payees across any merchant or financial institution."""
    # 1. If transaction already has a clean human-readable payee (mixed case, not processor string), keep it
    if current_payee and not current_payee.isupper():
        if not any(
            current_payee.upper().startswith(pre)
            for pre in ("TST*", "PY *", "SQ *", "AMAZON", "PAYMENT THANK YOU")
        ):
            return current_payee.strip()

    # 2. Check high-confidence Plaid counterparties (excluding terminals like Toast / Square)
    if meta:
        counterparties = meta.get("counterparties") or []
        for cp in counterparties:
            if cp.get("type") in ("merchant", "financial_institution") and cp.get(
                "name"
            ):
                return cp["name"].strip()
        if meta.get("merchant_name"):
            return meta["merchant_name"].strip()

    # 3. Fall back to cleaning original name / raw payee
    raw = current_payee or orig or ""

    # Common delivery tip pattern
    if re.search(r"AMAZON\s*TIPS\*", raw, re.IGNORECASE):
        return "Whole Foods"

    # Strip bank/processor prefixes
    p = re.sub(
        r"^(TST\*\s*|PY\s*\*|SQ\s*\*|POS\s+DEBIT\s+|DEBIT\s+CARD\s+PURCHASE\s+|PURCHASE\s+AUTHORIZED\s+ON\s+|AMAZON\s+(MKTPL|RETA)\*\s*|PAYMENT\s+THANK\s+YOU\s*-?\s*|CHASE\s+CREDIT\s+CRD\s+|MOBILE\s+PMT\s+|ACH\s+DEP\s+)",
        "",
        raw,
        flags=re.IGNORECASE,
    )

    # Strip URLs and trailing alphanumeric order tokens (e.g. *5Q6K570G0, .COM/US)
    p = re.sub(r"\.COM(/\w+)?", "", p, flags=re.IGNORECASE)
    p = re.sub(r"\*[A-Z0-9]{5,}.*$", "", p)
    p = re.sub(r"\s+-\s+.*$", "", p)
    p = re.sub(r"\s+#\d+.*$", "", p)
    p = p.strip(" -*#")

    # Clean payroll tokens (e.g. "C211238 UNSTRUCT PAYROLL" -> "Unstructured", "BRILLIANCE TECHN PAYROLL" -> "Brilliance Technologies")
    p = re.sub(r"^C\d+\s+", "", p)
    p = re.sub(r"\s+PAYROLL$", "", p, flags=re.IGNORECASE)
    p = re.sub(r"\s+TECHN$", " Technologies", p, flags=re.IGNORECASE)
    p = re.sub(r"^UNSTRUCT$", "Unstructured", p, flags=re.IGNORECASE)

    return p.title() if p.isupper() else p


class CategoryMatcher:
    """Builds a semantic lookup tree from the user's live category list."""

    def __init__(self, categories: list[dict[str, Any]]):
        self.categories = categories
        self.leaf_categories = [c for c in categories if not c.get("is_group")]
        self.groups = {c["id"]: c for c in categories if c.get("is_group")}

        # Build lower-case lookup table
        self.by_name: dict[str, int] = {
            c["name"].lower().strip(): c["id"] for c in self.leaf_categories
        }

        # Build group children lookup
        self.group_children: dict[int, list[dict[str, Any]]] = {}
        for c in self.leaf_categories:
            gid = c.get("group_id")
            if gid:
                self.group_children.setdefault(gid, []).append(c)

    def find_best_leaf(self, *preferred_names: str) -> tuple[int | None, str]:
        """Find the best matching leaf/child category by preferred keyword candidates."""
        for name in preferred_names:
            target = name.lower().strip()
            # Exact name match
            if target in self.by_name:
                cid = self.by_name[target]
                cname = next(c["name"] for c in self.leaf_categories if c["id"] == cid)
                return cid, cname
            # Substring match
            for c in self.leaf_categories:
                if target in c["name"].lower() or c["name"].lower() in target:
                    return c["id"], c["name"]
        return None, "Uncategorized"

    def match(
        self,
        tx: dict[str, Any],
        current_category: dict[str, Any] | None = None,
    ) -> tuple[int | None, str, str | None]:
        """Universally classify a transaction into the user's best child category."""
        orig = (tx.get("original_name") or "").upper()
        payee = (tx.get("payee") or "").upper()
        meta = tx.get("plaid_metadata") or {}
        pfc = meta.get("personal_finance_category") or {}
        detailed = pfc.get("detailed", "").upper()
        primary = pfc.get("primary", "").upper()
        plaid_cats = [c.upper() for c in meta.get("category") or []]
        amt = float(tx.get("amount", 0))

        # 1. Credit Card Payments & Account Transfers
        if (
            "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT" in detailed
            or "TRANSFER_IN_CASH_ADVANCES" in detailed
            or "PAYMENT THANK YOU" in orig
            or "MOBILE PMT" in orig
            or "CREDIT CRD EPAY" in orig
        ):
            cid, cname = self.find_best_leaf(
                "Payment, Transfer", "Transfers", "Credit Card Payment"
            )
            return cid, cname, tx.get("notes") or "Credit Card Payment"

        # 2. Payroll / Wages
        if "INCOME_WAGES" in detailed or "PAYROLL" in orig or "PAYROLL" in payee:
            cid, cname = self.find_best_leaf("Salary", "Wages", "Paycheck", "Income")
            return cid, cname, tx.get("notes") or "Salary"

        # 3. Interest & Dividends
        if "INCOME_INTEREST_EARNED" in detailed or "INTEREST" in orig:
            cid, cname = self.find_best_leaf(
                "Bank Fees", "Interest", "Interest Income", "Income"
            )
            return cid, cname, tx.get("notes") or "Interest"

        if "DIVIDEND" in orig:
            cid, cname = self.find_best_leaf(
                "Bank Fees", "Dividends", "Investment Income", "Investment"
            )
            return cid, cname, "Dividend"

        if "REINVESTMENT" in orig:
            cid, cname = self.find_best_leaf("Bank Fees", "Reinvestment", "Investment")
            return cid, cname, "Reinvestment"

        # 4. Groceries / Supermarkets
        if (
            "GROCERIES" in detailed
            or any("GROCERIES" in c or "SUPERMARKET" in c for c in plaid_cats)
            or "WHOLE FOODS" in orig
            or "SAFEWAY" in orig
        ):
            cid, cname = self.find_best_leaf(
                "Groceries", "Supermarkets", "Food & Groceries"
            )
            note = "Delivery Tip" if "TIPS" in orig else tx.get("notes")
            return cid, cname, note

        # 5. Food & Drink: Bars, Coffee, Fast Food, Takeout, Restaurants
        if "BEER_WINE_AND_LIQUOR" in detailed or any(
            "BAR" in c or "LIQUOR" in c for c in plaid_cats
        ):
            cid, cname = self.find_best_leaf(
                "Alcohol, Bars", "Bars", "Alcohol", "Drinks"
            )
            return cid, cname, tx.get("notes")

        if primary == "FOOD_AND_DRINK" or any("FOOD" in c for c in plaid_cats):
            if "COFFEE" in detailed:
                cid, cname = self.find_best_leaf(
                    "Coffee Shops", "Coffee", "Cafes", "Restaurants"
                )
                return cid, cname, tx.get("notes")
            if "FAST_FOOD" in detailed or any(
                fast in orig
                for fast in (
                    "CHIPOTLE",
                    "MENDOCINO",
                    "ACAI",
                    "DOORDASH",
                    "UBER EATS",
                    "GRUBHUB",
                )
            ):
                cid, cname = self.find_best_leaf(
                    "Takeout", "Fast Food", "Food Delivery", "Restaurants", "Dining"
                )
                return cid, cname, tx.get("notes")
            cid, cname = self.find_best_leaf("Restaurants", "Dining Out", "Dining")
            return cid, cname, tx.get("notes")

        # 6. Kids & Childcare
        if (
            "KIDS" in orig
            or "KIDS" in payee
            or "HANNA ANDERSSON" in orig
            or "Kids' Store" in meta.get("category", [])
        ):
            cid, cname = self.find_best_leaf(
                "Kids", "Childcare", "Children", "Family", "Shopping"
            )
            return cid, cname, tx.get("notes")

        # 7. Student Loans / Mortgage / Regular Bills
        if "STUDENT_LOAN" in detailed:
            cid, cname = self.find_best_leaf("Student Loans", "Bills", "Debt", "Loans")
            return cid, cname, tx.get("notes") or "Student Loan"

        # 8. Shopping & General Merchandise
        if primary == "GENERAL_MERCHANDISE" or "SHOPS" in plaid_cats:
            cid, cname = self.find_best_leaf(
                "Shopping", "Merchandise", "General Merchandise"
            )
            note = "Refund" if amt < 0 else tx.get("notes")
            return cid, cname, note

        # Fallback to current attached leaf category if valid
        if current_category and not current_category.get("is_group"):
            return (
                current_category["id"],
                current_category.get("name", "Current"),
                tx.get("notes"),
            )

        cur_cid = tx.get("category_id")
        if cur_cid in [c["id"] for c in self.leaf_categories]:
            cname = next(c["name"] for c in self.leaf_categories if c["id"] == cur_cid)
            return cur_cid, cname, tx.get("notes")

        return None, "Uncategorized", tx.get("notes")


def find_actual_recurring_matches(
    tx: dict[str, Any],
    prop_payee: str,
    actual_recurring_items: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], str]]:
    """Universally scan actual confirmed recurring items with strict amount and category validation."""
    amt = float(tx.get("amount", 0))
    orig = (tx.get("original_name") or "").lower()
    payee = prop_payee.lower()
    results = []
    seen_ids = set()

    for item in actual_recurring_items:
        if item.get("status") == "suggested":
            continue

        i_id = item["id"]
        if i_id in seen_ids:
            continue

        crit = item.get("transaction_criteria") or {}
        ovr = item.get("overrides") or {}
        r_payee = (ovr.get("payee") or crit.get("payee") or "").lower()
        r_amt_str = crit.get("amount")
        r_cat_id = ovr.get("category_id") or crit.get("category_id")
        if not r_payee:
            continue

        try:
            r_amt = float(r_amt_str) if r_amt_str is not None else None
        except ValueError:
            r_amt = None

        payee_match = (
            r_payee in payee or payee in r_payee or r_payee in orig or orig in r_payee
        )

        if not payee_match:
            continue

        # Prevent credit card payment transfers from matching mortgage/loans/bills
        if any(
            term in orig
            for term in ("credit crd", "payment thank you", "mobile pmt", "credit card")
        ):
            if r_cat_id and r_amt and abs(abs(amt) - abs(r_amt)) > 10.0:
                continue

        # 1. Exact Amount Match
        if r_amt is not None and abs(abs(amt) - abs(r_amt)) < 0.01:
            results.append((item, "Exact amount & payee match"))
            seen_ids.add(i_id)
            continue

        # 2. Variable Salary Match (only for confirmed salary deposits)
        if (
            ("payroll" in orig or "payroll" in payee or "salary" in payee)
            and ("payroll" in r_payee or "salary" in r_payee)
            and amt < 0
        ):
            results.append((item, "Salary deposit match"))
            seen_ids.add(i_id)
            continue

    return results


def process_review_data(
    data: dict[str, Any] | list[Any],
    output_updates_path: Path | None = None,
    recurring_items_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Process review data dictionary or list and optionally save bulk update payload."""
    if isinstance(data, dict):
        raw_items = data.get("transactions", [])
        categories = data.get("categories", [])
        accounts = data.get("accounts", {})
    else:
        raw_items = data
        categories = []
        accounts = {}

    recurring_items = []
    if recurring_items_path and recurring_items_path.exists():
        try:
            r_data = json.loads(recurring_items_path.read_text())
            all_items = (
                r_data
                if isinstance(r_data, list)
                else r_data.get("recurring_items", [])
            )
            recurring_items = [i for i in all_items if i.get("status") != "suggested"]
        except Exception:
            pass

    matcher = CategoryMatcher(categories)
    plaid_accs = {
        a["id"]: a.get("display_name") or a.get("name")
        for a in accounts.get("plaid_accounts", [])
    }

    updates = []
    recurring_matches = []

    print(f"\n### Unreviewed Transactions Review ({len(raw_items)} items)\n")
    print(
        "| ID | Date | Account | Amount | Raw Payee | Proposed Payee | Proposed Category | Proposed Notes |"
    )
    print("|:---|:---|:---|:---|:---|:---|:---|:---|")

    for item in raw_items:
        if isinstance(item, dict) and "transaction" in item:
            tx = item["transaction"]
            cur_cat = item.get("category")
            acc_info = item.get("plaid_account") or item.get("manual_account")
            acc = (
                acc_info.get("display_name") or acc_info.get("name")
                if acc_info
                else "Manual / Other"
            )
        else:
            tx = item
            cur_cat = None
            acc = plaid_accs.get(tx.get("plaid_account_id"), "Manual / Other")

        tid = tx["id"]
        date = tx.get("date")
        amt = float(tx.get("amount", 0))
        amt_str = f"-${abs(amt):.2f}" if amt < 0 else f"${amt:.2f}"
        raw_payee = tx.get("payee")
        raw_orig = tx.get("original_name")
        meta = tx.get("plaid_metadata")

        prop_payee = clean_universal_payee(raw_payee, raw_orig, meta)
        cat_id, cat_name, prop_notes = matcher.match(tx, cur_cat)

        # Check actual recurring items
        if recurring_items:
            matches = find_actual_recurring_matches(tx, prop_payee, recurring_items)
            for r_item, r_type in matches:
                r_crit = r_item.get("transaction_criteria") or {}
                r_ovr = r_item.get("overrides") or {}
                r_name = r_ovr.get("payee") or r_crit.get("payee") or "Recurring Item"
                r_cadence = r_crit.get("granularity", "month")
                recurring_matches.append(
                    (
                        tid,
                        date,
                        prop_payee,
                        amt_str,
                        r_item["id"],
                        r_name,
                        r_cadence,
                        r_type,
                    )
                )

        update_rec = {
            "id": tid,
            "payee": prop_payee,
            "category_id": cat_id,
            "notes": prop_notes,
            "status": "reviewed",
        }
        updates.append(update_rec)

        cat_display = f"**{cat_name}** (`{cat_id}`)" if cat_id else "*(None)*"
        notes_display = f"`{prop_notes}`" if prop_notes else "—"
        display_raw = raw_payee or raw_orig or ""
        print(
            f"| `{tid}` | {date} | {acc} | {amt_str} | {display_raw} | {prop_payee} | {cat_display} | {notes_display} |"
        )

    if recurring_matches:
        print("\n### 🔄 Matched Actual Recurring Items")
        print(
            "The following transactions match actual recurring items in your Lunch Money account:"
        )
        for (
            r_tid,
            r_date,
            r_payee,
            r_amt,
            r_id,
            r_name,
            r_cadence,
            r_type,
        ) in recurring_matches:
            print(
                f"- **Tx `{r_tid}`** ({r_payee}, {r_amt}) $\\rightarrow$ Recurring Item **`{r_id}`** (*{r_name}*, {r_cadence}ly) — *{r_type}*"
            )
        print(
            "\n*Would you like to link any of these transactions to their recurring item (`recurring_id`)?*"
        )

    if output_updates_path:
        output_updates_path.parent.mkdir(parents=True, exist_ok=True)
        output_updates_path.write_text(json.dumps({"transactions": updates}, indent=2))
        print(f"\n> Prepared bulk update payload saved to `{output_updates_path}`")

    return updates


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: process_review.py <path_to_review_transactions_output.json> [path_to_save_bulk_updates.json] [path_to_recurring_items.json]"
        )
        sys.exit(1)

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    rec_src = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    data = json.loads(src.read_text())
    process_review_data(data, dst, rec_src)
