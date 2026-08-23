"""Tests for the vendored Lunch Money application module."""

from pathlib import Path
from collections.abc import AsyncIterator
import asyncio
import threading
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, AsyncMock, MagicMock, create_autospec

import sys
import pytest
from lunchmoney_app.app import app as fastapi_app
from lunchmoney_app import client as app_module

app_main_module = sys.modules["lunchmoney_app.app.main"]
lifespan_module = sys.modules["lunchmoney_app.app.lifespan"]


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
    from lunchmoney_app.client import LunchMoneyApp

    assert LunchMoneyApp.__name__ == "LunchMoneyApp"


def test_app_initializes_instance_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Store the constructor cache setting on each application instance."""
    app = create_app(monkeypatch, cache=False)

    assert app.cache is False


def test_app_preserves_explicit_empty_model_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allow callers to intentionally disable default refresh models and kwargs."""
    monkeypatch.setattr(app_module, "LunchableClient", lambda **kwargs: object())

    app = app_module.LunchMoneyApp(
        access_token="token",
        lunchable_models=[],
        lunchable_models_kwargs={},
    )

    assert list(app._lunchable_models) == []
    assert app._lunchable_models_kwargs == {}


def test_app_rejects_nonpositive_transaction_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject pagination settings that cannot advance an upstream query."""
    monkeypatch.setattr(app_module, "LunchableClient", lambda **kwargs: object())

    with pytest.raises(ValueError, match="greater than zero"):
        app_module.LunchMoneyApp(access_token="token", transaction_pagination=0)


@pytest.mark.asyncio
async def test_refresh_without_cache_does_not_replace_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return refreshed categories without replacing the cached categories."""
    from lunchmoney_app.client import (
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
    from lunchmoney_app.client import CategoryObject

    app = create_app(monkeypatch)
    app.refresh = AsyncMock()

    await app.refresh_data(models=[CategoryObject], cache=False)

    app.refresh.assert_awaited_once_with(CategoryObject, cache=False)


@pytest.mark.asyncio
async def test_refresh_data_inherits_cache_from_app_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve an omitted bulk-refresh cache setting from the instance."""
    from lunchmoney_app.client import CategoryObject

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
    from lunchmoney_app.client import (
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
    from lunchmoney_app.database import LunchMoneyDatabase
    from lunchmoney_app.database.models import Transaction, User
    from database.factories import (
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

        from lunchmoney_app.app import sync_database

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


def test_fastapi_api_root_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return the API greeting from the namespaced root endpoint."""
    from starlette.testclient import TestClient

    monkeypatch.setattr(app_module, "LunchableClient", lambda **kwargs: object())
    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "mock-token")

    with TestClient(fastapi_app, base_url="http://localhost") as client:
        response = client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Hello World"


@pytest.mark.asyncio
async def test_explicit_sync_request_skips_automatic_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reserve the sync endpoint's single refresh for its requested date window."""
    from contextlib import asynccontextmanager

    from starlette.requests import Request
    from starlette.responses import Response

    operation_count = 0

    @asynccontextmanager
    async def fake_operation() -> AsyncIterator[object]:
        """Bind a lifecycle that performs no implicit synchronization."""
        nonlocal operation_count
        operation_count += 1
        yield object()

    async def call_next(_: Request) -> Response:
        """Return a successful response from the simulated request handler."""
        return Response(status_code=200)

    monkeypatch.setattr(
        app_main_module,
        "_operation_factory",
        lambda: SimpleNamespace(operation=fake_operation),
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/sync",
            "headers": [],
            "query_string": b"days=14",
        }
    )

    response = await app_main_module.bind_data_operation(request, call_next)

    assert response.status_code == 200
    assert operation_count == 1


@pytest.mark.asyncio
async def test_rest_maps_stateful_mode_boundary_to_conflict_contract() -> None:
    """Expose one safe REST error for dashboard and synchronization boundaries."""
    import json

    from starlette.requests import Request

    from lunchmoney_app.services.errors import StatefulModeRequired

    response = await app_main_module.stateful_mode_required_handler(
        Request({"type": "http", "method": "GET", "path": "/", "headers": []}),
        StatefulModeRequired(),
    )

    assert response.status_code == 409
    assert json.loads(response.body) == {
        "detail": {
            "code": "stateful_mode_required",
            "message": "This operation requires stateful persistence mode.",
        }
    }


@pytest.mark.asyncio
async def test_rest_rejects_ephemeral_stateful_route_before_client_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject stateful-only routes before constructing upstream dependencies."""
    from starlette.requests import Request

    from lunchmoney_app.config import RuntimeSettings
    from lunchmoney_app.services.errors import StatefulModeRequired

    settings = RuntimeSettings(persistence_mode="ephemeral")
    operation_factory = create_autospec(
        app_main_module._operation_factory,
        side_effect=AssertionError("client resolved"),
    )
    monkeypatch.setattr(app_main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(app_main_module, "_operation_factory", operation_factory)

    with pytest.raises(StatefulModeRequired):
        await app_main_module.bind_data_operation(
            Request(
                {
                    "type": "http",
                    "method": "POST",
                    "path": "/api/sync",
                    "headers": [],
                }
            ),
            AsyncMock(),
        )

    operation_factory.assert_not_called()


def test_fastapi_api_key_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject REST requests without the configured API key."""
    from starlette.testclient import TestClient

    from lunchmoney_app.config import get_secret_settings, get_settings

    monkeypatch.setattr(app_module, "LunchableClient", lambda **kwargs: object())
    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "mock-token")
    monkeypatch.setenv("LUNCHMONEY_APP_API_KEY", "rest-api-key")
    get_secret_settings.cache_clear()
    get_settings.cache_clear()

    with TestClient(fastapi_app, base_url="http://localhost") as client:
        assert client.get("/api").status_code == 401
        assert client.get("/api", headers={"X-API-Key": "wrong"}).status_code == 401
        response = client.get("/api", headers={"X-API-Key": "rest-api-key"})

    assert response.status_code == 200
    get_secret_settings.cache_clear()
    get_settings.cache_clear()


def test_fastapi_sync_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trigger migrations and sync via the /api/sync endpoint."""
    from starlette.testclient import TestClient

    migrations_ran = False

    async def mock_migrations(database_url: str | None = None) -> None:
        nonlocal migrations_ran
        migrations_ran = True

    async def mock_sync(
        client: Any,
        db: Any,
        days: int = 30,
        incremental: bool = False,
        safety_margin_minutes: int | None = None,
        scope: Any = None,
    ) -> app_module.SyncSummary:
        assert incremental is False
        assert safety_margin_minutes is None
        return app_module.SyncSummary(user=1, transactions=5)

    import lunchmoney_app.services.sync as sync_service_module

    monkeypatch.setattr(sync_service_module, "run_migrations", mock_migrations)
    monkeypatch.setattr(sync_service_module, "sync_database", mock_sync)
    monkeypatch.setattr(app_module, "LunchableClient", lambda **kwargs: object())
    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "mock-token")

    with TestClient(fastapi_app, base_url="http://localhost") as client:
        response = client.post("/api/sync?days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Synchronization complete"
        assert data["synced"]["user"] == 1
        assert data["synced"]["transactions"] == 5
        assert migrations_ran is True


def test_fastapi_sync_endpoint_forwards_incremental_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward incremental query controls unchanged to the sync service."""
    from lunchmoney_app.schemas import SyncDetails, SyncResponse
    from starlette.testclient import TestClient

    sync_router_module = sys.modules["lunchmoney_app.app.routers.sync"]
    mock_execute_sync = AsyncMock(
        return_value=SyncResponse(
            synced=SyncDetails(
                user=0,
                plaid_accounts=0,
                manual_accounts=0,
                categories=0,
                tags=0,
                transactions=0,
                total=0,
            )
        )
    )
    monkeypatch.setattr(sync_router_module, "execute_sync", mock_execute_sync)
    monkeypatch.setattr(app_module, "LunchableClient", lambda **kwargs: object())
    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "mock-token")

    with TestClient(fastapi_app, base_url="http://localhost") as client:
        response = client.post(
            "/api/sync?days=14&incremental=true&safety_margin_minutes=9"
        )

    assert response.status_code == 200
    mock_execute_sync.assert_awaited_once_with(
        db=ANY,
        client=ANY,
        days=14,
        incremental=True,
        safety_margin_minutes=9,
    )


@pytest.mark.parametrize(
    "query",
    ["days=0", "days=-1", "safety_margin_minutes=-1"],
)
def test_fastapi_sync_endpoint_rejects_invalid_windows(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
) -> None:
    """Reject sync windows that could omit or invert upstream data."""
    from starlette.testclient import TestClient

    sync_router_module = sys.modules["lunchmoney_app.app.routers.sync"]
    mock_execute_sync = AsyncMock()
    monkeypatch.setattr(sync_router_module, "execute_sync", mock_execute_sync)
    monkeypatch.setattr(app_module, "LunchableClient", lambda **kwargs: object())
    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "mock-token")

    with TestClient(fastapi_app, base_url="http://localhost") as client:
        response = client.post(f"/api/sync?{query}")

    assert response.status_code == 422
    mock_execute_sync.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("days", "safety_margin_minutes", "message"),
    [
        (0, None, "days"),
        (30, -1, "safety_margin_minutes"),
    ],
)
async def test_execute_sync_rejects_invalid_windows_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    days: int,
    safety_margin_minutes: int | None,
    message: str,
) -> None:
    """Enforce sync window invariants for every non-HTTP caller."""
    import lunchmoney_app.services.sync as sync_service_module

    migrations = AsyncMock()
    sync_database_mock = AsyncMock()
    monkeypatch.setattr(sync_service_module, "run_migrations", migrations)
    monkeypatch.setattr(sync_service_module, "sync_database", sync_database_mock)

    with pytest.raises(ValueError, match=message):
        await sync_service_module.execute_sync(
            db=MagicMock(database_url="sqlite+aiosqlite:///stateful.db"),
            client=MagicMock(),
            days=days,
            safety_margin_minutes=safety_margin_minutes,
        )

    migrations.assert_not_awaited()
    sync_database_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_sync_forwards_incremental_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward incremental controls from the shared service to sync policy."""
    from lunchmoney_app.client import LunchMoneyApp, SyncSummary
    from lunchmoney_app.database import LunchMoneyDatabase
    import lunchmoney_app.services.sync as sync_service_module

    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.database_url = "sqlite+aiosqlite:///stateful.db"
    client = create_autospec(LunchMoneyApp, instance=True)
    sync_database_mock = AsyncMock(return_value=SyncSummary())
    migrations = AsyncMock()
    monkeypatch.setattr(sync_service_module, "run_migrations", migrations)
    monkeypatch.setattr(sync_service_module, "sync_database", sync_database_mock)

    await sync_service_module.execute_sync(
        db=database,
        client=client,
        days=45,
        incremental=True,
        safety_margin_minutes=7,
    )

    sync_database_mock.assert_awaited_once_with(
        db=database,
        client=client,
        days=45,
        incremental=True,
        safety_margin_minutes=7,
        scope=sync_service_module.SyncScope.ALL,
    )
    migrations.assert_awaited_once_with(database_url=database.database_url)


@pytest.mark.asyncio
async def test_execute_sync_does_not_block_event_loop_while_waiting_for_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Let an owning sync progress while a concurrent caller waits for its lock."""
    import lunchmoney_app.services.sync as sync_service_module

    acquire_started = threading.Event()
    allow_acquire = threading.Event()

    class WaitingLock:
        """Block acquisition in a worker thread until the test releases it."""

        renewal_interval = None

        def __init__(self, timeout: float | int = -1) -> None:
            """Accept the lock factory's configured timeout."""
            del timeout

        def acquire(self, blocking: bool = True, timeout: float | int = -1) -> bool:
            """Wait for the simulated owner to finish."""
            del blocking, timeout
            acquire_started.set()
            return allow_acquire.wait(timeout=2)

        def release(self) -> None:
            """Release the acquired test lock."""

    monkeypatch.setattr(sync_service_module, "get_migration_lock", WaitingLock)
    monkeypatch.setattr(sync_service_module, "run_migrations", AsyncMock())
    monkeypatch.setattr(
        sync_service_module,
        "sync_database",
        AsyncMock(return_value=sync_service_module.SyncSummary()),
    )
    database = MagicMock(database_url="sqlite+aiosqlite:///stateful.db")
    database.delete_cached_responses = AsyncMock()

    sync_task = asyncio.create_task(
        sync_service_module.execute_sync(db=database, client=MagicMock())
    )
    assert await asyncio.to_thread(acquire_started.wait, 1)
    event_loop_progressed = asyncio.Event()
    asyncio.get_running_loop().call_soon(event_loop_progressed.set)
    await asyncio.wait_for(event_loop_progressed.wait(), timeout=0.2)
    allow_acquire.set()
    await sync_task


@pytest.mark.asyncio
async def test_execute_sync_stops_when_redis_lease_is_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancel projection work instead of overlapping after lease renewal fails."""
    import lunchmoney_app.services.sync as sync_service_module

    class LostLeaseLock:
        """Model an acquired lease that is rejected at its first renewal."""

        renewal_interval = 0.01

        def __init__(self, timeout: float | int = -1) -> None:
            """Accept the lock factory's configured timeout."""
            del timeout

        def acquire(self, blocking: bool = True, timeout: float | int = -1) -> bool:
            """Acquire the initial lease."""
            del blocking, timeout
            return True

        def renew(self) -> bool:
            """Report that another worker can no longer be excluded."""
            return False

        def release(self) -> None:
            """Release any remaining owned state."""

    async def blocked_sync(**kwargs: object) -> None:
        """Represent projection work that must be cancelled on ownership loss."""
        del kwargs
        await asyncio.Event().wait()

    monkeypatch.setattr(sync_service_module, "get_migration_lock", LostLeaseLock)
    monkeypatch.setattr(sync_service_module, "run_migrations", AsyncMock())
    monkeypatch.setattr(sync_service_module, "sync_database", blocked_sync)
    database = MagicMock(database_url="sqlite+aiosqlite:///stateful.db")

    with pytest.raises(sync_service_module.LockOwnershipLostError):
        await asyncio.wait_for(
            sync_service_module.execute_sync(db=database, client=MagicMock()),
            timeout=0.5,
        )


@pytest.mark.asyncio
async def test_explicit_sync_initializes_configured_memory_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Create the in-memory schema during sync when startup has not run."""
    from database.factories import user_object
    from lunchmoney_app.client import (
        CategoryObject,
        LunchMoneyApp,
        ManualAccountObject,
        PlaidAccountObject,
        TagObject,
        UserObject,
    )
    from lunchmoney_app.config import get_settings
    from lunchmoney_app.database import LunchMoneyDatabase, User
    from lunchmoney_app.services.sync import execute_sync

    async def refresh(model: type[Any]) -> Any:
        """Return a synthetic user and empty collections for other domains."""
        if model is UserObject:
            return user_object()
        if model in {
            PlaidAccountObject,
            ManualAccountObject,
            CategoryObject,
            TagObject,
        }:
            return {}
        raise AssertionError(f"Unexpected model refresh: {model}")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LUNCHMONEY_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    from lunchmoney_app.client import LunchableData

    client = AsyncMock(spec=LunchMoneyApp)
    client.data = LunchableData()
    client.refresh.side_effect = refresh
    client.refresh_transactions.return_value = {}

    try:
        async with LunchMoneyDatabase("sqlite+aiosqlite:///:memory:") as database:
            response = await execute_sync(db=database, client=client)
            persisted_user = await database.get(User, 1)

        assert response.synced.user == 1
        assert persisted_user is not None
        assert persisted_user.name == "Synthetic User"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_execute_mcp_sync_forwards_incremental_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward incremental controls through the MCP-facing shared service."""
    from lunchmoney_app.client import LunchMoneyApp
    from lunchmoney_app.database import LunchMoneyDatabase
    from lunchmoney_app.schemas import SyncDetails, SyncResponse
    import lunchmoney_app.services.sync as sync_service_module

    database = create_autospec(LunchMoneyDatabase, instance=True)
    client = create_autospec(LunchMoneyApp, instance=True)
    execute_sync_mock = AsyncMock(
        return_value=SyncResponse(
            message="Synchronization complete",
            synced=SyncDetails(
                user=0,
                plaid_accounts=0,
                manual_accounts=0,
                categories=0,
                tags=0,
                transactions=0,
                total=0,
            ),
        )
    )
    monkeypatch.setattr(sync_service_module, "execute_sync", execute_sync_mock)

    await sync_service_module.execute_mcp_sync(
        db=database,
        client=client,
        days=45,
        incremental=True,
        safety_margin_minutes=7,
    )

    execute_sync_mock.assert_awaited_once_with(
        db=database,
        client=client,
        days=45,
        incremental=True,
        safety_margin_minutes=7,
    )


@pytest.mark.asyncio
async def test_fastapi_database_dependencies(tmp_path: Path) -> None:
    """Require a bound context before resolving a database dependency."""
    from lunchmoney_app.app import get_database, get_db_session
    from lunchmoney_app.database import LunchMoneyDatabase
    from sqlmodel.ext.asyncio.session import AsyncSession

    with pytest.raises(RuntimeError, match="No data operation"):
        get_database()

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

    with TestClient(fastapi_app, base_url="http://localhost") as client:
        response = client.get("/api")
        assert response.status_code == 200
        assert migrations_ran is True


def test_stateful_memory_sqlite_startup_syncs_and_persists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Initialize an explicitly configured stateful memory SQLite backend."""
    from lunchmoney_app.app.dependencies import get_database
    from lunchmoney_app.client import (
        CategoryObject,
        ManualAccountObject,
        PlaidAccountObject,
        TagObject,
        UserObject,
    )
    from lunchmoney_app.config import get_settings
    from starlette.testclient import TestClient
    from database.factories import user_object

    async def mock_refresh(
        self: app_module.LunchMoneyApp,
        model: type[Any],
    ) -> Any:
        """Return a synthetic user and empty collections for other domains."""
        if model is UserObject:
            return user_object()
        if model in {
            PlaidAccountObject,
            ManualAccountObject,
            CategoryObject,
            TagObject,
        }:
            return {}
        raise AssertionError(f"Unexpected model refresh: {model}")

    async def mock_refresh_transactions(
        self: app_module.LunchMoneyApp,
        **kwargs: Any,
    ) -> dict[int, Any]:
        """Return no transactions while exercising the real sync service."""
        return {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "mock-token")
    monkeypatch.setenv(
        "LUNCHMONEY_DATABASE_URL",
        "sqlite+aiosqlite:///file:test-stateful-memory?mode=memory&cache=shared&uri=true",
    )
    monkeypatch.setattr(app_module, "LunchableClient", lambda **kwargs: object())
    monkeypatch.setattr(app_module.LunchMoneyApp, "refresh", mock_refresh)
    monkeypatch.setattr(
        app_module.LunchMoneyApp,
        "refresh_transactions",
        mock_refresh_transactions,
    )
    get_settings.cache_clear()
    get_database.cache_clear()

    try:
        with TestClient(fastapi_app, base_url="http://localhost") as client:
            empty_user = client.get("/api/user")
            sync_response = client.post("/api/sync?days=30")
            persisted_user = client.get("/api/user")

        assert empty_user.status_code == 200
        assert empty_user.json() is None
        assert sync_response.status_code == 200
        assert sync_response.json()["synced"]["user"] == 1
        assert persisted_user.status_code == 200
        assert persisted_user.json()["name"] == "Synthetic User"
    finally:
        get_settings.cache_clear()
        get_database.cache_clear()


def test_openapi_docs_served_at_api_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expose OpenAPI documentation at /api/docs, /api/redoc, and /api/openapi.json without auth."""
    from starlette.testclient import TestClient
    from lunchmoney_app.app import auth as auth_module

    monkeypatch.setattr(
        auth_module,
        "get_secret_settings",
        lambda: SimpleNamespace(mcp_api_key="secret-key"),
    )
    with TestClient(fastapi_app, base_url="http://localhost") as client:
        docs = client.get("/api/docs")
        redoc = client.get("/api/redoc")
        openapi = client.get("/api/openapi.json")

    assert docs.status_code == 200
    assert redoc.status_code == 200
    assert openapi.status_code == 200
    assert "SwaggerUIBundle" in docs.text
    assert "redoc" in redoc.text.lower()
    assert openapi.json()["info"]["title"] == "Lunch Money MCP"


def test_html_responses_disable_browser_caching() -> None:
    """Attach no-cache headers to HTML responses to prevent stale browser renders."""
    from starlette.testclient import TestClient

    with TestClient(fastapi_app, base_url="http://localhost") as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Expires"] == "0"
