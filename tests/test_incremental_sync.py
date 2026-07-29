"""Integration tests for incremental synchronization metadata."""

import datetime
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from lunchmoney_mcp.database import LunchMoneyDatabase, SyncMetadata, run_migrations


@pytest_asyncio.fixture
async def database(tmp_path: Path) -> AsyncIterator[LunchMoneyDatabase]:
    """Provide a fresh migrated database for incremental metadata tests."""
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'incremental-sync.db'}"
    await run_migrations(database_url)
    async with LunchMoneyDatabase(database_url) as test_database:
        yield test_database


@pytest.mark.asyncio
async def test_sync_metadata_is_upserted_by_domain(
    database: LunchMoneyDatabase,
) -> None:
    """Replace and reload the watermark identified by one domain."""
    timestamp = datetime.datetime(2026, 7, 28, tzinfo=datetime.UTC)
    stored = await database.upsert_sync_metadata(
        SyncMetadata(domain="transactions", last_synced_at=timestamp)
    )
    assert stored.last_synced_at == timestamp
    assert (await database.get_sync_metadata("transactions")) == stored


@pytest.mark.asyncio
async def test_sync_metadata_upsert_replaces_domain_watermark(
    database: LunchMoneyDatabase,
) -> None:
    """Replace the previous watermark when the domain already exists."""
    original = SyncMetadata(
        domain="transactions",
        last_synced_at=datetime.datetime(2026, 7, 27, tzinfo=datetime.UTC),
    )
    replacement = SyncMetadata(
        domain="transactions",
        last_synced_at=datetime.datetime(2026, 7, 28, tzinfo=datetime.UTC),
    )

    await database.upsert_sync_metadata(original)
    stored = await database.upsert_sync_metadata(replacement)

    assert stored.last_synced_at == replacement.last_synced_at
    assert (await database.get_sync_metadata("transactions")) == replacement


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        (
            datetime.datetime(2026, 7, 28, 10, 0),
            datetime.datetime(2026, 7, 28, 10, 0, tzinfo=datetime.UTC),
        ),
        (
            datetime.datetime(
                2026,
                7,
                28,
                10,
                0,
                tzinfo=datetime.timezone(datetime.timedelta(hours=-6)),
            ),
            datetime.datetime(2026, 7, 28, 16, 0, tzinfo=datetime.UTC),
        ),
    ],
)
@pytest.mark.asyncio
async def test_sync_metadata_normalizes_watermarks_to_utc(
    database: LunchMoneyDatabase,
    timestamp: datetime.datetime,
    expected: datetime.datetime,
) -> None:
    """Normalize naive and offset-aware watermarks before persistence."""
    metadata = SyncMetadata(domain="transactions", last_synced_at=timestamp)

    assert metadata.last_synced_at == expected
    assert metadata.last_synced_at.tzinfo is datetime.UTC

    stored = await database.upsert_sync_metadata(metadata)

    assert stored.last_synced_at == expected
    assert stored.last_synced_at.tzinfo is datetime.UTC
    assert (await database.get_sync_metadata("transactions")) == stored
