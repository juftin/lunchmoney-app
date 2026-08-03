"""Integration and service tests for the server-rendered dashboard."""

import datetime
import importlib
from types import SimpleNamespace
from typing import cast
from unittest.mock import ANY, AsyncMock, create_autospec

import pytest
from lunchmoney.models import BudgetSettingsResponseObject, SummaryResponseObject
from starlette.testclient import TestClient

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.app.main import fastapi_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import SyncMetadata
from lunchmoney_mcp.schemas import (
    AccountInfo,
    AccountsSummary,
    GroupedSpendingResponse,
    ScheduledSyncStatus,
    TransactionInfo,
)
from lunchmoney_mcp.services.dashboard import DashboardData


auth_module = importlib.import_module("lunchmoney_mcp.app.auth")
dashboard_router = importlib.import_module("lunchmoney_mcp.app.routers.dashboard")
dashboard_service = importlib.import_module("lunchmoney_mcp.services.dashboard")


def _budget_settings() -> BudgetSettingsResponseObject:
    """Create valid synthetic budget settings for dashboard rendering."""
    return BudgetSettingsResponseObject.model_validate(
        {
            "budget_period_granularity": "month",
            "budget_period_quantity": 1,
            "budget_period_anchor_date": "2026-01-01",
            "budget_hide_no_activity": False,
            "budget_use_last_day_of_month": False,
            "budget_income_option": "activity",
            "budget_rollover_left_to_budget": False,
        }
    )


def _dashboard_data(*, unavailable_sections: tuple[str, ...] = ()) -> DashboardData:
    """Create populated synthetic content for the dashboard template."""
    return DashboardData(
        period_start=datetime.date(2026, 8, 1),
        period_end=datetime.date(2026, 8, 2),
        previous_period_start=datetime.date(2026, 7, 1),
        next_period_start=None,
        transaction_last_synced_at=datetime.datetime(
            2026, 8, 2, 12, tzinfo=datetime.timezone.utc
        ),
        accounts=AccountsSummary(
            plaid_accounts=[
                AccountInfo(
                    id=1,
                    name="Checking",
                    balance=1250.50,
                    currency="usd",
                )
            ]
        ),
        budget_summary=SummaryResponseObject.model_validate(
            {"aligned": True, "categories": []}
        ),
        budget_settings=_budget_settings(),
        category_spending=GroupedSpendingResponse.model_validate(
            {
                "start_date": "2026-07-03",
                "end_date": "2026-08-02",
                "total_spending": 20,
                "total_income": 0,
                "categories": [
                    {
                        "category_id": 1,
                        "category_name": "Groceries",
                        "is_group": False,
                        "is_income": False,
                        "total_amount": 20,
                        "transaction_count": 1,
                        "children": [],
                    }
                ],
            }
        ),
        transactions=[
            TransactionInfo(
                id=1,
                date=datetime.date(2026, 8, 2),
                payee="<Synthetic payee>",
                amount=20,
                currency="usd",
                status="cleared",
            )
        ],
        scheduled_sync=ScheduledSyncStatus(
            status="success",
            started_at=datetime.datetime(2026, 8, 2, 11, tzinfo=datetime.timezone.utc),
            finished_at=datetime.datetime(2026, 8, 2, 12, tzinfo=datetime.timezone.utc),
        ),
        unavailable_sections=unavailable_sections,
    )


def _configure_dashboard(
    monkeypatch: pytest.MonkeyPatch,
    data: DashboardData,
) -> None:
    """Patch the dashboard's dependencies with isolated rendering fixtures."""
    monkeypatch.setattr(
        dashboard_router,
        "fetch_dashboard_data",
        AsyncMock(return_value=data),
    )
    monkeypatch.setattr(
        auth_module,
        "get_secret_settings",
        lambda: SimpleNamespace(mcp_api_key="dashboard-key"),
    )
    fastapi_app.dependency_overrides[get_database] = lambda: object()
    fastapi_app.dependency_overrides[get_lunchmoney_app] = lambda: object()


def test_dashboard_requires_api_key_and_renders_populated_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Protect dashboard HTML and render accessible populated content when authorized."""
    _configure_dashboard(monkeypatch=monkeypatch, data=_dashboard_data())
    try:
        with TestClient(fastapi_app, base_url="http://localhost") as client:
            assert client.get("/").status_code == 401
            response = client.get("/", headers={"X-API-Key": "dashboard-key"})
    finally:
        fastapi_app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="dashboard-content"' in response.text
    assert "cockpit-layout" in response.text
    assert "Spending breakdown" in response.text
    assert "dashboard.js" in response.text
    assert "Period summary" in response.text
    assert "Checking" in response.text
    assert "Groceries" in response.text
    assert "&lt;Synthetic payee&gt;" in response.text
    with TestClient(fastapi_app, base_url="http://localhost") as client:
        stylesheet = client.get("/static/dashboard.css")
        tabler_stylesheet = client.get("/static/vendor/tabler/tabler.min.css")
        script = client.get("/static/dashboard.js")
    assert stylesheet.status_code == 200
    assert "spending-workspace" in stylesheet.text
    assert tabler_stylesheet.status_code == 200
    assert "Tabler" in tabler_stylesheet.text
    assert script.status_code == 200
    assert "initializePanelSwitcher" in script.text


def test_dashboard_renders_empty_and_unavailable_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Render readable empty and partial-error states instead of JSON failures."""
    data = _dashboard_data(unavailable_sections=("Budget status",))
    data = DashboardData(
        period_start=data.period_start,
        period_end=data.period_end,
        previous_period_start=data.previous_period_start,
        next_period_start=data.next_period_start,
        transaction_last_synced_at=None,
        accounts=AccountsSummary(),
        budget_summary=None,
        budget_settings=None,
        category_spending=GroupedSpendingResponse(
            start_date=data.period_start,
            end_date=data.period_end,
            total_spending=0,
            total_income=0,
            categories=[],
        ),
        transactions=[],
        scheduled_sync=None,
        unavailable_sections=data.unavailable_sections,
    )
    _configure_dashboard(monkeypatch=monkeypatch, data=data)
    try:
        with TestClient(fastapi_app, base_url="http://localhost") as client:
            response = client.get("/", headers={"X-API-Key": "dashboard-key"})
    finally:
        fastapi_app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Partial data" in response.text
    assert "No cached accounts yet" in response.text
    assert "Your ledger is quiet" in response.text


def test_dashboard_passes_the_requested_period_to_its_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward a requested period date to the dashboard data loader."""
    _configure_dashboard(monkeypatch=monkeypatch, data=_dashboard_data())
    try:
        with TestClient(fastapi_app, base_url="http://localhost") as client:
            response = client.get(
                "/?period=2026-07-16", headers={"X-API-Key": "dashboard-key"}
            )
    finally:
        fastapi_app.dependency_overrides.clear()

    assert response.status_code == 200
    dashboard_router.fetch_dashboard_data.assert_awaited_once_with(
        db=ANY,
        client=ANY,
        period_start=datetime.date(2026, 7, 16),
    )


@pytest.mark.asyncio
async def test_dashboard_service_keeps_other_sections_available_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep cached content renderable when one live dashboard section fails."""
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.get_sync_metadata = AsyncMock(
        return_value=SyncMetadata(
            domain="transactions",
            last_synced_at=datetime.datetime(2026, 8, 2, tzinfo=datetime.timezone.utc),
        )
    )
    database.get_latest_scheduled_sync_run = AsyncMock(return_value=None)
    accounts = AccountsSummary()
    spending = GroupedSpendingResponse(
        start_date=datetime.date(2026, 7, 3),
        end_date=datetime.date(2026, 8, 2),
        total_spending=0,
        total_income=0,
        categories=[],
    )
    monkeypatch.setattr(
        dashboard_service,
        "fetch_accounts",
        AsyncMock(return_value=accounts),
    )
    monkeypatch.setattr(
        dashboard_service,
        "fetch_account_summary",
        AsyncMock(side_effect=RuntimeError("upstream unavailable")),
    )
    monkeypatch.setattr(
        dashboard_service,
        "fetch_budget_settings",
        AsyncMock(return_value=_budget_settings()),
    )
    monkeypatch.setattr(
        dashboard_service,
        "fetch_category_spending",
        AsyncMock(return_value=spending),
    )
    monkeypatch.setattr(
        dashboard_service,
        "fetch_recent_transactions",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        dashboard_service,
        "get_scheduled_sync_status",
        AsyncMock(return_value=None),
    )

    data = await dashboard_service.fetch_dashboard_data(
        db=database,
        client=cast(LunchMoneyApp, object()),
        period_start=datetime.date(2026, 7, 16),
    )

    assert data.budget_summary is None
    assert data.accounts == accounts
    assert data.transaction_last_synced_at is not None
    assert data.unavailable_sections == ("Budget status",)
    assert data.period_start == datetime.date(2026, 7, 1)
    assert data.period_end == datetime.date(2026, 7, 31)
    dashboard_service.fetch_category_spending.assert_awaited_once_with(
        db=database,
        start_date=datetime.date(2026, 7, 1),
        end_date=datetime.date(2026, 7, 31),
        days=None,
    )
    dashboard_service.fetch_recent_transactions.assert_awaited_once_with(
        db=database,
        limit=10,
        start_date=datetime.date(2026, 7, 1),
        end_date=datetime.date(2026, 7, 31),
    )
