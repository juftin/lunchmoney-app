"""Opt-in integration checks against Lunch Money's official static mock."""

import os
from datetime import date

import pytest

from lunchmoney_mcp.client import LunchableClient

MOCK_SERVICE_URL = "https://mock.lunchmoney.dev/v2"
"""Lunch Money's official static mock service, which has no financial data."""
SYNTHETIC_TOKEN = "mock-contract-token"
"""Non-secret bearer token accepted by the static mock service."""


@pytest.mark.upstream_contract
@pytest.mark.asyncio
async def test_mock_service_supports_every_read_only_endpoint_group() -> None:
    """Exercise all read-only endpoint groups without accessing a real budget."""
    if os.getenv("RUN_LUNCHMONEY_CONTRACT_TESTS") != "1":
        pytest.skip("Set RUN_LUNCHMONEY_CONTRACT_TESTS=1 to call the public mock.")

    client = LunchableClient(access_token=SYNTHETIC_TOKEN)
    client.configuration.host = MOCK_SERVICE_URL

    await client.me.get_me()
    await client.categories.get_all_categories()
    await client.manual_accounts.get_all_manual_accounts()
    await client.plaid.get_all_plaid_accounts()
    await client.tags.get_all_tags()
    await client.transactions_bulk.get_all_transactions()
    await client.recurring_items.get_all_recurring()
    await client.summary.get_budget_summary(
        start_date=date(2026, 7, 1), end_date=date(2026, 7, 31), include_totals=True
    )
    await client.budgets.get_budget_settings()
