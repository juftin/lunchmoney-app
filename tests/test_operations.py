"""Tests for mode-specific operation contexts and memoization."""

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest

from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.services.adapters.base import OperationMemo
from lunchmoney_app.services.errors import StatefulModeRequired
from lunchmoney_app.services.operations import (
    EphemeralOperationContextFactory,
    StatefulOperationContextFactory,
    clear_unpersisted_stale_domains,
    get_operation_context,
    get_unpersisted_stale_domains,
    get_stateful_operation_context,
)


def _client() -> LunchMoneyApp:
    """Return a synthetic client sufficient for context construction."""
    return cast(LunchMoneyApp, SimpleNamespace(client=SimpleNamespace()))


@pytest.mark.asyncio
async def test_ephemeral_context_constructs_no_database_and_resets() -> None:
    """Bind live collaborators without storage and clear access on exit."""
    factory = EphemeralOperationContextFactory(_client())

    async with factory.operation() as context:
        assert context.mode == "ephemeral"
        assert get_operation_context() is context
        with pytest.raises(StatefulModeRequired):
            get_stateful_operation_context()

    with pytest.raises(RuntimeError, match="No data operation"):
        get_operation_context()


@pytest.mark.asyncio
async def test_stateful_context_binds_supplied_database_without_disposal() -> None:
    """Bind the exact shared database and leave its lifecycle to the runtime."""
    database = Mock(spec=LunchMoneyDatabase)
    factory = StatefulOperationContextFactory(_client(), database)

    async with factory.operation() as context:
        assert context.mode == "stateful"
        assert context.database is database
        assert get_stateful_operation_context() is context

    with pytest.raises(RuntimeError, match="No data operation"):
        get_stateful_operation_context()
    with pytest.raises(RuntimeError, match="no longer active"):
        _ = context.database
    assert not database.dispose.called


@pytest.mark.asyncio
async def test_context_resets_after_operation_failure() -> None:
    """Reset ambient context even when an operation raises."""
    factory = EphemeralOperationContextFactory(_client())

    with pytest.raises(ValueError, match="synthetic"):
        async with factory.operation():
            raise ValueError("synthetic")

    with pytest.raises(RuntimeError, match="No data operation"):
        get_operation_context()


@pytest.mark.asyncio
async def test_context_is_revoked_in_child_task_after_operation_exit() -> None:
    """Reject inherited ContextVar state and retained collaborators after teardown."""
    factory = EphemeralOperationContextFactory(_client())
    release = asyncio.Event()

    async def inherited_access() -> str:
        """Wait until teardown before attempting to use inherited context state."""
        await release.wait()
        with pytest.raises(RuntimeError, match="no longer active"):
            get_operation_context()
        return "rejected"

    async with factory.operation() as context:
        task = asyncio.create_task(inherited_access())

    release.set()
    assert await task == "rejected"
    with pytest.raises(RuntimeError, match="no longer active"):
        await context.accounts.list()


@pytest.mark.asyncio
async def test_operation_memo_coalesces_and_copies_successes() -> None:
    """Coalesce equivalent concurrent reads and isolate returned values."""
    memo = OperationMemo()
    loader = AsyncMock(return_value=[{"id": 1}])

    first, second = await asyncio.gather(
        memo.get_or_create(("transactions:list", 1), loader),
        memo.get_or_create(("transactions:list", 1), loader),
    )

    assert loader.await_count == 1
    assert first == second
    assert first is not second
    first.append({"id": 2})
    assert second == [{"id": 1}]


@pytest.mark.asyncio
async def test_operation_memo_does_not_cache_failures_and_invalidates_prefix() -> None:
    """Retry failed loads and discard successful entries after mutation."""
    memo = OperationMemo()
    loader = AsyncMock(side_effect=[ValueError("failure"), [1], [2]])

    with pytest.raises(ValueError, match="failure"):
        await memo.get_or_create(("categories:list",), loader)
    assert await memo.get_or_create(("categories:list",), loader) == [1]
    memo.invalidate("categories")
    assert await memo.get_or_create(("categories:list",), loader) == [2]
    assert loader.await_count == 3


@pytest.mark.asyncio
async def test_projection_failure_preserves_success_and_marks_domain_stale() -> None:
    """Keep an upstream success authoritative while degrading cache health."""
    database = Mock(spec=LunchMoneyDatabase)
    database.upsert_cached_response = AsyncMock()
    factory = StatefulOperationContextFactory(_client(), database)

    async with factory.operation() as context:
        result = await context.project(
            "transactions", AsyncMock(side_effect=RuntimeError("projection"))()
        )

    assert result is None
    database.upsert_cached_response.assert_awaited_once_with(
        "health:stale:transactions", {"stale": True}
    )


@pytest.mark.asyncio
async def test_successful_projection_clears_stale_domain_marker() -> None:
    """Restore cache health after a later successful domain projection."""
    database = Mock(spec=LunchMoneyDatabase)
    database.delete_cached_responses = AsyncMock()
    factory = StatefulOperationContextFactory(_client(), database)

    async with factory.operation() as context:
        assert await context.project("categories", AsyncMock(return_value=7)()) == 7

    database.delete_cached_responses.assert_awaited_once_with("health:stale:categories")


@pytest.mark.asyncio
async def test_projection_marker_failure_retains_process_local_stale_health() -> None:
    """Keep readiness degraded when a durable stale marker cannot be written."""
    clear_unpersisted_stale_domains()
    database = Mock(spec=LunchMoneyDatabase)
    database.upsert_cached_response = AsyncMock(side_effect=RuntimeError("unavailable"))
    factory = StatefulOperationContextFactory(_client(), database)

    try:
        async with factory.operation() as context:
            await context.project(
                "transactions", AsyncMock(side_effect=RuntimeError("projection"))()
            )

        assert get_unpersisted_stale_domains() == {"transactions"}
    finally:
        clear_unpersisted_stale_domains()
