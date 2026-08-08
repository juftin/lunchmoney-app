"""Tests for persistence-mode operation lifecycles."""

from unittest.mock import ANY, AsyncMock, Mock

import pytest

from lunchmoney_mcp.config import RuntimeSettings
from lunchmoney_mcp.services.operations import data_operation, get_operation_database


@pytest.mark.asyncio
async def test_ephemeral_operation_refreshes_and_disposes_private_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use one private, refreshed database and clear it after the operation."""
    import lunchmoney_mcp.services.operations as operations

    database = Mock()
    database.create_tables = AsyncMock()
    database.dispose = AsyncMock()
    sync_database = AsyncMock()
    monkeypatch.setattr(operations, "LunchMoneyDatabase", Mock(return_value=database))
    monkeypatch.setattr(operations, "sync_database", sync_database)
    monkeypatch.setattr(
        operations, "get_settings", lambda: RuntimeSettings(ephemeral=True)
    )

    async with data_operation(client=Mock(), database=None) as active:
        assert active is database
        assert get_operation_database() is database

    database.create_tables.assert_awaited_once()
    sync_database.assert_awaited_once_with(db=database, client=ANY, days=30)
    database.dispose.assert_awaited_once()
    assert get_operation_database() is None


@pytest.mark.asyncio
async def test_shared_operation_does_not_dispose_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep durable database lifecycle outside individual operations."""
    import lunchmoney_mcp.services.operations as operations

    database = Mock()
    monkeypatch.setattr(operations, "get_settings", lambda: RuntimeSettings())

    async with data_operation(client=Mock(), database=database) as active:
        assert active is database
        assert get_operation_database() is database

    assert get_operation_database() is None
