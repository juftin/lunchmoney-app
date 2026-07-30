"""Regression tests for Sprint 4 budget and spending-trend features."""

import sys
from types import SimpleNamespace
from typing import cast
from unittest.mock import ANY, AsyncMock

import pytest
from lunchmoney.models import BudgetSettingsResponseObject

from lunchmoney_mcp.app.main import fastapi_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.mcp import mcp
from lunchmoney_mcp.services import fetch_budget_settings


def _budget_settings() -> BudgetSettingsResponseObject:
    """Create a valid budget-settings response for live-query tests."""
    return BudgetSettingsResponseObject.model_validate(
        {
            "budget_period_granularity": "month",
            "budget_period_quantity": 1,
            "budget_period_anchor_date": "2026-01-01",
            "budget_hide_no_activity": False,
            "budget_use_last_day_of_month": True,
            "budget_income_option": "activity",
            "budget_rollover_left_to_budget": False,
        }
    )


@pytest.mark.asyncio
async def test_budget_settings_service_forwards_to_lunch_money_client() -> None:
    """Fetch budget settings from the generated Lunch Money API client."""
    settings = _budget_settings()
    get_budget_settings = AsyncMock(return_value=settings)
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                budgets=SimpleNamespace(get_budget_settings=get_budget_settings)
            )
        ),
    )

    result = await fetch_budget_settings(client=client)

    assert result == settings
    get_budget_settings.assert_awaited_once_with()


def test_budget_settings_route_is_registered() -> None:
    """Publish the budget-settings endpoint in the OpenAPI document."""
    operation = fastapi_app.openapi()["paths"]["/budgets/settings"]["get"]

    assert operation["operationId"] == "get_budget_settings"


@pytest.mark.asyncio
async def test_budget_settings_mcp_tool_delegates_to_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delegate the MCP budget-settings tool to the budget service."""
    budget_tools = sys.modules["lunchmoney_mcp.mcp.tools.budgets"]
    fetch_settings = AsyncMock(return_value=_budget_settings())
    monkeypatch.setattr(budget_tools, "fetch_budget_settings", fetch_settings)
    monkeypatch.setattr(budget_tools, "get_lunchmoney_app", object)

    await mcp.call_tool("get_budget_settings", {})

    fetch_settings.assert_awaited_once_with(client=ANY)
