"""Tests for the vendored Lunch Money application module."""

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import sys
import pytest
from lunchmoney_mcp.app import app as fastapi_app
from lunchmoney_mcp import client as app_module

app_main_module = sys.modules["lunchmoney_mcp.app.main"]
lifespan_module = sys.modules["lunchmoney_mcp.app.lifespan"]


def create_app(
    monkeypatch: pytest.MonkeyPatch, *, cache: bool = True
) -> app_module.LunchMoneyApp:
    """Create an initialized app with its network client patched out."""
    monkeypatch.setattr(app_module, "LunchableClient", lambda **kwargs: object())
    return app_module.LunchMoneyApp(access_token="token", cache=cache)


if TYPE_CHECKING:

    async def assert_refresh_overload_types(app: app_module.LunchMoneyApp) -> None:
        """Type-check model-specific refresh return values."""
        user: app_module.UserObject = await app.refresh(app_module.UserObject)
        transactions: dict[int, app_module.TransactionObject] = await app.refresh(
            app_module.TransactionObject
        )
        categories: dict[int, app_module.CategoryObject] = await app.refresh(
            app_module.CategoryObject
        )

        assert user
        assert transactions
        assert categories


def test_vendored_app_exports_lunch_money_app() -> None:
    """Expose the upstream application class from the package module."""
    from lunchmoney_mcp.client import LunchMoneyApp

    assert LunchMoneyApp.__name__ == "LunchMoneyApp"


def test_app_initializes_instance_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Store the constructor cache setting on each application instance."""
    app = create_app(monkeypatch, cache=False)

    assert app.cache is False


@pytest.mark.asyncio
async def test_refresh_without_cache_does_not_replace_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return refreshed categories without replacing the cached categories."""
    from lunchmoney_mcp.client import (
        CategoryObject,
        _ObjectMapper,
    )

    category = SimpleNamespace(id=1)

    async def get_all_categories(**kwargs: object) -> SimpleNamespace:
        """Return one known category response."""
        return SimpleNamespace(categories=[category])

    app = create_app(monkeypatch)
    monkeypatch.setattr(
        app_module.LunchMoneyApp,
        "_model_mapping",
        {
            CategoryObject: _ObjectMapper(
                func=get_all_categories,
                data_attr="categories",
            )
        },
    )
    result = await app.refresh(CategoryObject, cache=False)

    assert result == {1: category}
    assert app.data.categories == {}


@pytest.mark.asyncio
async def test_refresh_data_forwards_cache_to_each_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward the cache control to every requested model refresh."""
    from lunchmoney_mcp.client import CategoryObject

    app = create_app(monkeypatch)
    app.refresh = AsyncMock()

    await app.refresh_data(models=[CategoryObject], cache=False)

    app.refresh.assert_awaited_once_with(CategoryObject, cache=False)


@pytest.mark.asyncio
async def test_refresh_data_inherits_cache_from_app_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve an omitted bulk-refresh cache setting from the instance."""
    from lunchmoney_mcp.client import CategoryObject

    app = create_app(monkeypatch, cache=False)
    app.refresh = AsyncMock()

    await app.refresh_data(models=[CategoryObject])

    app.refresh.assert_awaited_once_with(CategoryObject, cache=False)


@pytest.mark.asyncio
async def test_refresh_transactions_without_cache_does_not_update_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return refreshed transactions without updating the cached transactions."""

    transaction = SimpleNamespace(id=1)

    async def paginate_transactions(
        self: app_module.LunchMoneyApp, **kwargs: object
    ) -> object:
        """Yield one known transaction."""
        yield transaction

    app = create_app(monkeypatch)
    monkeypatch.setattr(
        app_module.LunchMoneyApp,
        "_paginate_transactions",
        paginate_transactions,
    )

    result = await app.refresh_transactions(cache=False)

    assert result == {1: transaction}
    assert app.data.transactions == {}


@pytest.mark.asyncio
async def test_refresh_inherits_cache_from_app_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use an instance cache default when refresh cache is omitted."""
    from lunchmoney_mcp.client import (
        CategoryObject,
        _ObjectMapper,
    )

    category = SimpleNamespace(id=1)

    async def get_all_categories(**kwargs: object) -> SimpleNamespace:
        """Return one known category response."""
        return SimpleNamespace(categories=[category])

    app = create_app(monkeypatch, cache=False)
    monkeypatch.setattr(
        app_module.LunchMoneyApp,
        "_model_mapping",
        {
            CategoryObject: _ObjectMapper(
                func=get_all_categories,
                data_attr="categories",
            )
        },
    )
    result = await app.refresh(CategoryObject)

    assert result == {1: category}
    assert app.data.categories == {}


@pytest.mark.asyncio
async def test_refresh_transactions_inherits_cache_from_app_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use an instance cache default when transaction cache is omitted."""

    transaction = SimpleNamespace(id=1)

    async def paginate_transactions(
        self: app_module.LunchMoneyApp, **kwargs: object
    ) -> object:
        """Yield one known transaction."""
        yield transaction

    app = create_app(monkeypatch, cache=False)
    monkeypatch.setattr(
        app_module.LunchMoneyApp,
        "_paginate_transactions",
        paginate_transactions,
    )

    result = await app.refresh_transactions()

    assert result == {1: transaction}
    assert app.data.transactions == {}


def test_sync_summary_total() -> None:
    """Calculate total synced records across entity types."""
    summary = app_module.SyncSummary(
        user=1,
        plaid_accounts=2,
        manual_accounts=1,
        categories=5,
        tags=3,
        transactions=10,
    )
    assert summary.total == 22


@pytest.mark.asyncio
async def test_sync_database_populates_last_30_days(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fetch 30-day window objects and persist them into database."""
    import datetime
    from lunchmoney_mcp.database import LunchMoneyDatabase
    from lunchmoney_mcp.database.models import Transaction, User
    from tests.database.factories import (
        category_object,
        plaid_account_object,
        transaction_object,
        user_object,
    )

    api_user = user_object()
    api_plaid = plaid_account_object()
    api_category = category_object()
    api_txn = transaction_object(transaction_id=101, tag_ids=[])

    app = create_app(monkeypatch)

    async def mock_refresh(self: app_module.LunchMoneyApp, model: Any) -> Any:
        if model is app_module.UserObject:
            return api_user
        if model is app_module.PlaidAccountObject:
            return {api_plaid.id: api_plaid}
        if model is app_module.CategoryObject:
            return {api_category.id: api_category}
        return {}

    async def mock_refresh_txns(
        self: app_module.LunchMoneyApp,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
        **kwargs: Any,
    ) -> dict[int, app_module.TransactionObject]:
        assert start_date is not None
        assert end_date is not None
        assert (end_date - start_date).days == 30
        return {101: api_txn}

    monkeypatch.setattr(app_module.LunchMoneyApp, "refresh", mock_refresh)
    monkeypatch.setattr(
        app_module.LunchMoneyApp, "refresh_transactions", mock_refresh_txns
    )

    db_path = tmp_path / "sync.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    async with LunchMoneyDatabase(db_url) as db:
        # Create schema tables for the test DB
        async with db.engine.begin() as conn:
            from sqlmodel import SQLModel

            await conn.run_sync(SQLModel.metadata.create_all)

        from lunchmoney_mcp.app import sync_database

        summary = await sync_database(db=db, client=app, days=30)

        assert summary.user == 1
        assert summary.plaid_accounts == 1
        assert summary.categories == 1
        assert summary.transactions == 1
        assert summary.total == 4

        db_user = await db.get(User, 1)
        assert db_user is not None
        assert db_user.name == "Synthetic User"

        db_txn = await db.get(Transaction, 101)
        assert db_txn is not None
        assert db_txn.payee == "Synthetic Parent Payee"


def test_fastapi_root_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return Hello World response from the root endpoint."""
    from starlette.testclient import TestClient

    monkeypatch.setattr(app_module, "LunchableClient", lambda **kwargs: object())
    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "mock-token")

    with TestClient(fastapi_app) as client:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Hello World"


def test_fastapi_sync_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trigger migrations and sync via the /sync endpoint."""
    from starlette.testclient import TestClient

    migrations_ran = False

    async def mock_migrations(database_url: str | None = None) -> None:
        nonlocal migrations_ran
        migrations_ran = True

    async def mock_sync(client: Any, db: Any, days: int = 30) -> app_module.SyncSummary:
        return app_module.SyncSummary(user=1, transactions=5)

    from lunchmoney_mcp.app.routers import sync as sync_router_module

    monkeypatch.setattr(sync_router_module, "run_migrations", mock_migrations)
    monkeypatch.setattr(sync_router_module, "sync_database", mock_sync)
    monkeypatch.setattr(app_module, "LunchableClient", lambda **kwargs: object())
    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "mock-token")

    with TestClient(fastapi_app) as client:
        response = client.post("/sync?days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Synchronization complete"
        assert data["synced"]["user"] == 1
        assert data["synced"]["transactions"] == 5
        assert migrations_ran is True


@pytest.mark.asyncio
async def test_fastapi_database_dependencies(tmp_path: Path) -> None:
    """Verify get_database and get_db_session dependencies yield expected instances."""
    from lunchmoney_mcp.app import get_database, get_db_session
    from lunchmoney_mcp.database import LunchMoneyDatabase
    from sqlmodel.ext.asyncio.session import AsyncSession

    db_instance = get_database()
    assert isinstance(db_instance, LunchMoneyDatabase)

    db_path = tmp_path / "dep.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    async with LunchMoneyDatabase(db_url) as test_db:
        sessions: list[AsyncSession] = []
        async for session in get_db_session(test_db):
            sessions.append(session)

        assert len(sessions) == 1
        assert isinstance(sessions[0], AsyncSession)


def test_fastapi_lifespan_migration_single_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify lifespan runs database migrations when filelock is acquired."""
    from starlette.testclient import TestClient

    migrations_ran = False

    async def mock_migrations(database_url: str | None = None) -> None:
        nonlocal migrations_ran
        migrations_ran = True

    monkeypatch.setattr(lifespan_module, "run_migrations", mock_migrations)

    with TestClient(fastapi_app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert migrations_ran is True
