"""Tests for Model Context Protocol (MCP) tools and Pydantic response models."""

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock

import pytest

from lunchmoney_mcp.config import RuntimeSettings
from lunchmoney_mcp.mcp import mcp
from lunchmoney_mcp.schemas import (
    CategoryInfo,
    RootResponse,
    SyncDetails,
    SyncResponse,
    SyncResult,
    UserInfo,
)


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
async def test_mcp_runtime_lifespan_creates_and_disposes_ephemeral_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Initialize in-memory tool storage only while standalone MCP is running."""
    import lunchmoney_mcp.mcp.app as mcp_app_module

    database = Mock()
    database.create_tables = AsyncMock()
    database.dispose = AsyncMock()
    get_database = Mock(return_value=database)
    monkeypatch.setattr(mcp_app_module, "get_database", get_database)
    monkeypatch.setattr(mcp_app_module, "get_runtime_mode", lambda: "mcp")
    monkeypatch.setattr(
        mcp_app_module, "get_settings", lambda: RuntimeSettings(ephemeral=False)
    )

    async with mcp_app_module.mcp_lifespan(mcp):
        database.create_tables.assert_awaited_once_with()

    database.dispose.assert_awaited_once_with()
    get_database.cache_clear.assert_called_once_with()


@pytest.mark.asyncio
async def test_mcp_runtime_lifespan_skips_storage_in_ephemeral_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave private per-operation storage to the MCP operation middleware."""
    import lunchmoney_mcp.mcp.app as mcp_app_module

    get_database = Mock()
    monkeypatch.setattr(mcp_app_module, "get_database", get_database)
    monkeypatch.setattr(mcp_app_module, "get_runtime_mode", lambda: "mcp")
    monkeypatch.setattr(
        mcp_app_module, "get_settings", lambda: RuntimeSettings(ephemeral=True)
    )

    async with mcp_app_module.mcp_lifespan(mcp):
        pass

    get_database.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_mcp_sync_skips_automatic_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Let the sync tool run only its caller-requested upstream synchronization."""
    import lunchmoney_mcp.mcp.operations as operations_module

    observed_refresh: list[bool] = []

    @asynccontextmanager
    async def fake_data_operation(**kwargs: Any) -> AsyncIterator[object]:
        """Record lifecycle refresh settings without creating application storage."""
        observed_refresh.append(kwargs["refresh"])
        yield object()

    async def call_next(_: object) -> str:
        """Return a sentinel result from the simulated MCP tool."""
        return "synchronized"

    monkeypatch.setattr(operations_module, "data_operation", fake_data_operation)
    monkeypatch.setattr(operations_module, "get_lunchmoney_app", object)
    monkeypatch.setattr(operations_module, "get_shared_database", object)
    monkeypatch.setattr(operations_module, "get_settings", RuntimeSettings)
    context = SimpleNamespace(message=SimpleNamespace(name="sync_data"))

    result = await operations_module.DataOperationMiddleware().on_call_tool(
        context, call_next
    )

    assert result == "synchronized"
    assert observed_refresh == [False]


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
    from lunchmoney_mcp.mcp import server

    mock_run = Mock()
    monkeypatch.setattr(server.mcp, "run", mock_run)
    monkeypatch.setattr(sys, "argv", ["lunchmoney-mcp", *arguments])

    server.main()

    if transport != "stdio":
        run_arguments["host"] = RuntimeSettings().host
        run_arguments["port"] = RuntimeSettings().port
    mock_run.assert_called_once_with(**run_arguments)


def test_mcp_main_forwards_http_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward HTTP bind options only to HTTP-based MCP transports."""
    from lunchmoney_mcp.mcp import server

    mock_run = Mock()
    monkeypatch.setattr(server.mcp, "run", mock_run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["lunchmoney-mcp", "--streamable-http", "--host", "0.0.0.0", "--port", "9000"],
    )

    server.main()

    mock_run.assert_called_once_with(
        transport="streamable-http", host="0.0.0.0", port=9000
    )


def test_mcp_main_rejects_multiple_transport_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject ambiguous CLI invocations with more than one transport flag."""
    from lunchmoney_mcp.mcp import server

    mock_run = Mock()
    monkeypatch.setattr(server.mcp, "run", mock_run)
    monkeypatch.setattr(sys, "argv", ["lunchmoney-mcp", "--stdio", "--sse"])

    with pytest.raises(SystemExit):
        server.main()

    mock_run.assert_not_called()


def test_mcp_main_rejects_http_bind_options_for_stdio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject HTTP bind options when the process-pipe transport is selected."""
    from lunchmoney_mcp.mcp import server

    mock_run = Mock()
    monkeypatch.setattr(server.mcp, "run", mock_run)
    monkeypatch.setattr(sys, "argv", ["lunchmoney-mcp", "--stdio", "--port", "9000"])

    with pytest.raises(SystemExit):
        server.main()

    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_sync_tool_forwards_incremental_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forward incremental tool arguments unchanged to the sync service."""
    sync_tool_module = sys.modules["lunchmoney_mcp.mcp.tools.sync"]
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
    monkeypatch.setattr(sync_tool_module, "get_database", object)
    monkeypatch.setattr(sync_tool_module, "get_lunchmoney_app", object)

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
