"""Tests for Model Context Protocol (MCP) tools and Pydantic response models."""

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock

import pytest

from lunchmoney_app.config import RuntimeSettings
from lunchmoney_app.mcp import mcp
from lunchmoney_app.schemas import (
    CategoryInfo,
    RootResponse,
    SyncDetails,
    SyncResponse,
    SyncResult,
    UserInfo,
)


@pytest.fixture(autouse=True)
def reset_runtime_configuration() -> None:
    """Keep standalone-MCP process settings from leaking into later tests."""
    import lunchmoney_app.config as config_module

    config_module._runtime_settings = None
    config_module._runtime_mode = None
    config_module.get_settings.cache_clear()
    yield
    config_module._runtime_settings = None
    config_module._runtime_mode = None
    config_module.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_mcp_tools_registration() -> None:
    """Verify all expected Lunch Money tools are registered on top-level FastMCP server."""
    tools = await mcp.list_tools()
    tool_names = {t.name for t in tools}

    assert "sync_data" in tool_names
    assert "get_sync_status" in tool_names
    assert "get_user_info" in tool_names
    assert "list_categories" in tool_names
    assert "list_manual_accounts" in tool_names
    assert "list_plaid_accounts" in tool_names
    assert "list_accounts" in tool_names
    assert "list_transactions" in tool_names
    assert "get_account_summary" in tool_names
    assert "list_tags" in tool_names
    assert "get_tag" in tool_names
    assert "list_recurring_items" in tool_names
    assert "get_recurring_item" in tool_names
    assert "get_category" in tool_names
    assert "get_manual_account" in tool_names
    assert "get_plaid_account" in tool_names
    assert "get_transaction" in tool_names


@pytest.mark.asyncio
async def test_mcp_resources_and_prompts_registration() -> None:
    """Publish Sprint 5 resources and prompts on the shared MCP server."""
    resource_uris = {str(resource.uri) for resource in await mcp.list_resources()}
    prompt_names = {prompt.name for prompt in await mcp.list_prompts()}

    assert "lunchmoney://summary" in resource_uris
    assert "lunchmoney://categories" in resource_uris
    assert "budget_health_check" in prompt_names
    assert "uncategorized_transactions_audit" in prompt_names


@pytest.mark.asyncio
async def test_mcp_runtime_lifespan_supports_explicit_stateful_memory_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Initialize in-memory tool storage only while standalone MCP is running."""
    import lunchmoney_app.mcp.app as mcp_app_module

    database = Mock()
    database.database_url = "sqlite+aiosqlite:///:memory:"
    database.create_tables = AsyncMock()
    database.dispose = AsyncMock()
    get_shared_database = Mock(return_value=database)
    monkeypatch.setattr(mcp_app_module, "get_shared_database", get_shared_database)
    monkeypatch.setattr(mcp_app_module, "get_runtime_mode", lambda: "mcp")
    monkeypatch.setattr(mcp_app_module, "get_settings", RuntimeSettings)
    monkeypatch.setattr(
        mcp_app_module,
        "get_secret_settings",
        lambda: SimpleNamespace(database_url_is_explicit=False),
    )

    async with mcp_app_module.mcp_lifespan(mcp):
        database.create_tables.assert_awaited_once_with()

    database.dispose.assert_awaited_once_with()
    get_shared_database.cache_clear.assert_called_once_with()


@pytest.mark.asyncio
async def test_stateful_mcp_lifespan_uses_real_shared_database_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Start stateful MCP storage without requiring an operation-bound context."""
    import lunchmoney_app.mcp.app as mcp_app_module
    from lunchmoney_app.app.dependencies import get_shared_database
    from lunchmoney_app.config import get_secret_settings
    from lunchmoney_app.database.models import User

    monkeypatch.setenv("LUNCHMONEY_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    get_secret_settings.cache_clear()
    get_shared_database.cache_clear()
    monkeypatch.setattr(mcp_app_module, "get_runtime_mode", lambda: "mcp")
    monkeypatch.setattr(mcp_app_module, "get_settings", RuntimeSettings)

    try:
        async with mcp_app_module.mcp_lifespan(mcp):
            assert await get_shared_database().list(User) == []
    finally:
        get_shared_database.cache_clear()
        get_secret_settings.cache_clear()


@pytest.mark.asyncio
async def test_mcp_runtime_lifespan_migrates_persistent_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apply migrations before serving a persistent standalone MCP endpoint."""
    import lunchmoney_app.mcp.app as mcp_app_module

    database = Mock(database_url="sqlite+aiosqlite:///stateful.db")
    database.dispose = AsyncMock()
    lock = Mock()
    lock.__enter__ = Mock(return_value=lock)
    lock.__exit__ = Mock(return_value=None)
    run_migrations = AsyncMock()
    monkeypatch.setattr(
        mcp_app_module, "get_shared_database", Mock(return_value=database)
    )
    monkeypatch.setattr(mcp_app_module, "get_runtime_mode", lambda: "mcp")
    monkeypatch.setattr(mcp_app_module, "get_settings", RuntimeSettings)
    monkeypatch.setattr(
        mcp_app_module,
        "get_secret_settings",
        lambda: SimpleNamespace(database_url_is_explicit=False),
    )
    monkeypatch.setattr(mcp_app_module, "get_migration_lock", Mock(return_value=lock))
    monkeypatch.setattr(mcp_app_module, "run_migrations", run_migrations)

    async with mcp_app_module.mcp_lifespan(mcp):
        pass

    run_migrations.assert_awaited_once_with()
    database.dispose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_mcp_runtime_lifespan_skips_storage_in_ephemeral_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Construct no storage in database-free ephemeral mode."""
    import lunchmoney_app.mcp.app as mcp_app_module

    get_shared_database = Mock()
    monkeypatch.setattr(mcp_app_module, "get_shared_database", get_shared_database)
    monkeypatch.setattr(mcp_app_module, "get_runtime_mode", lambda: "mcp")
    monkeypatch.setattr(
        mcp_app_module,
        "get_settings",
        lambda: RuntimeSettings.model_validate(
            {
                "persistence_mode": "ephemeral",
                "schedule_transactions_cron": None,
                "schedule_metadata_cron": None,
                "schedule_cron": None,
                "embed_scheduler": False,
            }
        ),
    )
    monkeypatch.setattr(
        mcp_app_module,
        "get_secret_settings",
        lambda: SimpleNamespace(database_url_is_explicit=False),
    )

    async with mcp_app_module.mcp_lifespan(mcp):
        pass

    get_shared_database.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_mcp_sync_skips_automatic_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Let the sync tool run only its caller-requested upstream synchronization."""
    import lunchmoney_app.mcp.operations as operations_module

    operation_count = 0

    @asynccontextmanager
    async def fake_operation() -> AsyncIterator[object]:
        """Bind a lifecycle that performs no implicit synchronization."""
        nonlocal operation_count
        operation_count += 1
        yield object()

    async def call_next(_: object) -> str:
        """Return a sentinel result from the simulated MCP tool."""
        return "synchronized"

    monkeypatch.setattr(
        operations_module,
        "_operation_factory",
        lambda: SimpleNamespace(operation=fake_operation),
    )
    context = SimpleNamespace(message=SimpleNamespace(name="sync_data"))

    result = await operations_module.DataOperationMiddleware().on_call_tool(
        context, call_next
    )

    assert result == "synchronized"
    assert operation_count == 1


@pytest.mark.asyncio
async def test_mcp_maps_stateful_mode_boundary_without_database_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return the shared structured mode error before resolving storage."""
    import lunchmoney_app.mcp.operations as operations_module

    from lunchmoney_app.services.errors import StatefulModeRequired

    settings = SimpleNamespace(persistence_mode="ephemeral")
    get_shared_database = Mock(side_effect=AssertionError("database accessed"))
    monkeypatch.setattr(operations_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        operations_module,
        "get_lunchmoney_app",
        Mock(side_effect=AssertionError("client accessed")),
    )
    monkeypatch.setattr(operations_module, "get_shared_database", get_shared_database)

    async def call_next(_: object) -> None:
        """Simulate one stateful-only tool boundary."""
        raise StatefulModeRequired

    result = await operations_module.DataOperationMiddleware().on_call_tool(
        SimpleNamespace(message=SimpleNamespace(name="sync_data")), call_next
    )

    assert result.is_error is True
    assert result.structured_content == {
        "code": "stateful_mode_required",
        "message": "This operation requires stateful persistence mode.",
    }
    get_shared_database.assert_not_called()


@pytest.mark.parametrize(
    ("arguments", "transport", "run_arguments"),
    [
        ([], "stdio", {"transport": "stdio"}),
        (["--stdio"], "stdio", {"transport": "stdio"}),
        (
            ["--sse"],
            "sse",
            {"transport": "sse", "host": None, "port": None},
        ),
        (
            ["--http"],
            "http",
            {"transport": "http", "host": None, "port": None},
        ),
        (
            ["--streamable-http"],
            "streamable-http",
            {"transport": "streamable-http", "host": None, "port": None},
        ),
    ],
)
def test_mcp_main_selects_requested_transport(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    transport: str,
    run_arguments: dict[str, str | int | None],
) -> None:
    """Launch the MCP server using each supported CLI transport selection."""
    from lunchmoney_app.mcp import server

    mock_run = Mock()
    monkeypatch.setattr(server.mcp, "run", mock_run)
    monkeypatch.setattr(sys, "argv", ["lunchmoney-app", *arguments])

    server.main()

    if transport != "stdio":
        run_arguments["host"] = RuntimeSettings().host
        run_arguments["port"] = RuntimeSettings().port
    mock_run.assert_called_once_with(**run_arguments)


def test_mcp_main_forwards_http_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward HTTP bind options only to HTTP-based MCP transports."""
    from lunchmoney_app.mcp import server

    mock_run = Mock()
    monkeypatch.setattr(server.mcp, "run", mock_run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["lunchmoney-app", "--streamable-http", "--host", "0.0.0.0", "--port", "9000"],
    )

    server.main()

    mock_run.assert_called_once_with(
        transport="streamable-http", host="0.0.0.0", port=9000
    )


def test_mcp_main_rejects_multiple_transport_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject ambiguous CLI invocations with more than one transport flag."""
    from lunchmoney_app.mcp import server

    mock_run = Mock()
    monkeypatch.setattr(server.mcp, "run", mock_run)
    monkeypatch.setattr(sys, "argv", ["lunchmoney-app", "--stdio", "--sse"])

    with pytest.raises(SystemExit):
        server.main()

    mock_run.assert_not_called()


def test_mcp_main_rejects_http_bind_options_for_stdio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject HTTP bind options when the process-pipe transport is selected."""
    from lunchmoney_app.mcp import server

    mock_run = Mock()
    monkeypatch.setattr(server.mcp, "run", mock_run)
    monkeypatch.setattr(sys, "argv", ["lunchmoney-app", "--stdio", "--port", "9000"])

    with pytest.raises(SystemExit):
        server.main()

    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_sync_tool_forwards_incremental_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward incremental tool arguments unchanged to the sync service."""
    sync_tool_module = sys.modules["lunchmoney_app.mcp.tools.sync"]
    mock_execute_mcp_sync = AsyncMock(
        return_value=SyncResult(
            synced_records=SyncDetails(
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
    monkeypatch.setattr(sync_tool_module, "execute_mcp_sync", mock_execute_mcp_sync)
    operation = SimpleNamespace(database=object(), client=object())
    monkeypatch.setattr(
        sync_tool_module,
        "get_stateful_operation_context",
        lambda: operation,
    )

    await mcp.call_tool(
        "sync_data",
        {
            "days": 14,
            "incremental": True,
            "safety_margin_minutes": 9,
        },
    )

    mock_execute_mcp_sync.assert_awaited_once_with(
        db=ANY,
        client=ANY,
        days=14,
        incremental=True,
        safety_margin_minutes=9,
    )


def test_pydantic_models() -> None:
    """Verify Pydantic models instantiate and validate correctly."""
    user = UserInfo(
        id=1,
        name="Test User",
        email="test@example.com",
        budget_name="My Budget",
        primary_currency="usd",
    )
    assert user.id == 1
    assert user.primary_currency == "usd"

    cat = CategoryInfo(
        id=10,
        name="Groceries",
        is_income=False,
        exclude_from_budget=False,
        exclude_from_totals=False,
        is_group=False,
    )
    assert cat.name == "Groceries"

    root_resp = RootResponse()
    assert root_resp.message == "Hello World"

    sync_resp = SyncResponse(
        message="Synchronization complete",
        synced=SyncDetails(
            user=1,
            plaid_accounts=2,
            manual_accounts=3,
            categories=4,
            tags=5,
            transactions=6,
            total=21,
        ),
    )
    assert sync_resp.synced.total == 21
