"""Integration tests for incremental synchronization metadata."""

import datetime
import importlib
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import event

from lunchmoney_app.app.sync import sync_database
from lunchmoney_app.client import LunchMoneyApp, UserObject
from lunchmoney_app.database import (
    Category,
    LunchMoneyDatabase,
    ManualAccount,
    PlaidAccount,
    RecurringItem,
    SyncMetadata,
    Transaction,
    Tag,
    User,
    run_migrations,
)


@pytest_asyncio.fixture
async def database(tmp_path: Path) -> AsyncIterator[LunchMoneyDatabase]:
    """Provide a fresh migrated database for incremental metadata tests."""
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'incremental-sync.db'}"
    await run_migrations(database_url)
    async with LunchMoneyDatabase(database_url) as test_database:
        yield test_database


@pytest.fixture
def client() -> AsyncMock:
    """Provide a client double with successful empty domain refreshes."""
    from database.factories import user_object
    from lunchmoney_app.client import LunchableData

    test_client = AsyncMock(spec=LunchMoneyApp)
    test_client.data = LunchableData()

    async def refresh(model: type[Any]) -> Any:
        """Return the required user object and empty collection domains."""
        if model is UserObject:
            return user_object()
        return {}

    test_client.refresh.side_effect = refresh
    test_client.refresh_transactions.return_value = {}
    return test_client


@pytest.mark.asyncio
async def test_sync_metadata_is_upserted_by_domain(
    database: LunchMoneyDatabase,
) -> None:
    """Replace and reload the watermark identified by one domain."""
    timestamp = datetime.datetime(2026, 7, 28, tzinfo=datetime.timezone.utc)
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
        last_synced_at=datetime.datetime(2026, 7, 27, tzinfo=datetime.timezone.utc),
    )
    replacement = SyncMetadata(
        domain="transactions",
        last_synced_at=datetime.datetime(2026, 7, 28, tzinfo=datetime.timezone.utc),
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
            datetime.datetime(2026, 7, 28, 10, 0, tzinfo=datetime.timezone.utc),
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
            datetime.datetime(2026, 7, 28, 16, 0, tzinfo=datetime.timezone.utc),
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
    assert metadata.last_synced_at.tzinfo is datetime.timezone.utc

    stored = await database.upsert_sync_metadata(metadata)

    assert stored.last_synced_at == expected
    assert stored.last_synced_at.tzinfo is datetime.timezone.utc
    assert (await database.get_sync_metadata("transactions")) == stored


@pytest.mark.asyncio
async def test_incremental_sync_subtracts_requested_safety_margin(
    database: LunchMoneyDatabase,
    client: AsyncMock,
) -> None:
    """Query from the stored watermark minus an explicit overlap margin."""
    watermark = datetime.datetime(2026, 7, 28, 12, 0, tzinfo=datetime.timezone.utc)
    await database.upsert_sync_metadata(
        SyncMetadata(domain="transactions", last_synced_at=watermark)
    )

    await sync_database(
        db=database,
        client=cast(LunchMoneyApp, client),
        incremental=True,
        safety_margin_minutes=7,
    )

    client.refresh_transactions.assert_awaited_once_with(
        updated_since=watermark - datetime.timedelta(minutes=7),
        cache=False,
    )


@pytest.mark.asyncio
async def test_incremental_sync_uses_configured_safety_margin(
    monkeypatch: pytest.MonkeyPatch,
    database: LunchMoneyDatabase,
    client: AsyncMock,
) -> None:
    """Use the configured overlap when the request omits an override."""
    sync_module = importlib.import_module("lunchmoney_app.app.sync")

    watermark = datetime.datetime(2026, 7, 28, 12, 0, tzinfo=datetime.timezone.utc)
    await database.upsert_sync_metadata(
        SyncMetadata(domain="transactions", last_synced_at=watermark)
    )
    monkeypatch.setattr(
        sync_module,
        "get_settings",
        lambda: SimpleNamespace(sync_safety_margin_minutes=11),
    )

    await sync_database(
        db=database,
        client=cast(LunchMoneyApp, client),
        incremental=True,
    )

    client.refresh_transactions.assert_awaited_once_with(
        updated_since=watermark - datetime.timedelta(minutes=11),
        cache=False,
    )


@pytest.mark.asyncio
async def test_incremental_sync_without_watermark_uses_date_range(
    database: LunchMoneyDatabase,
    client: AsyncMock,
) -> None:
    """Fall back to the requested date window before a watermark exists."""
    start_date = datetime.date(2026, 6, 1)
    end_date = datetime.date(2026, 7, 1)

    await sync_database(
        db=database,
        client=cast(LunchMoneyApp, client),
        start_date=start_date,
        end_date=end_date,
        incremental=True,
    )

    client.refresh_transactions.assert_awaited_once_with(
        start_date=start_date,
        end_date=end_date,
        cache=False,
    )


@pytest.mark.asyncio
async def test_successful_incremental_sync_creates_watermark_after_upsert(
    monkeypatch: pytest.MonkeyPatch,
    database: LunchMoneyDatabase,
    client: AsyncMock,
) -> None:
    """Advance the transaction watermark only after records are persisted."""
    events: list[str] = []
    original_reconcile = database.reconcile_sync_projection

    async def tracked_reconcile(**kwargs: Any) -> None:
        """Record completion of the data upsert."""
        await original_reconcile(**kwargs)
        events.append("records")

    monkeypatch.setattr(database, "reconcile_sync_projection", tracked_reconcile)
    started_at = datetime.datetime.now(datetime.timezone.utc)

    await sync_database(
        db=database,
        client=cast(LunchMoneyApp, client),
        incremental=True,
    )

    stored = await database.get_sync_metadata("transactions")
    assert stored is not None
    assert (
        started_at
        <= stored.last_synced_at
        <= datetime.datetime.now(datetime.timezone.utc)
    )
    assert events[0] == "records"
    assert len(events) == 1


@pytest.mark.asyncio
async def test_failed_incremental_sync_does_not_advance_watermark(
    database: LunchMoneyDatabase,
    client: AsyncMock,
) -> None:
    """Preserve an existing watermark when the transaction refresh fails."""
    watermark = datetime.datetime(2026, 7, 28, 12, 0, tzinfo=datetime.timezone.utc)
    await database.upsert_sync_metadata(
        SyncMetadata(domain="transactions", last_synced_at=watermark)
    )
    client.refresh_transactions.side_effect = RuntimeError("synthetic upstream failure")

    with pytest.raises(RuntimeError, match="synthetic upstream failure"):
        await sync_database(
            db=database,
            client=cast(LunchMoneyApp, client),
            incremental=True,
        )

    stored = await database.get_sync_metadata("transactions")
    assert stored is not None
    assert stored.last_synced_at == watermark


@pytest.mark.asyncio
async def test_failed_incremental_upsert_does_not_advance_watermark(
    monkeypatch: pytest.MonkeyPatch,
    database: LunchMoneyDatabase,
    client: AsyncMock,
) -> None:
    """Leave the watermark absent when persistence of refreshed data fails."""
    monkeypatch.setattr(
        database,
        "reconcile_sync_projection",
        AsyncMock(side_effect=RuntimeError("synthetic database failure")),
    )

    with pytest.raises(RuntimeError, match="synthetic database failure"):
        await sync_database(
            db=database,
            client=cast(LunchMoneyApp, client),
            incremental=True,
        )

    assert await database.get_sync_metadata("transactions") is None


@pytest.mark.asyncio
async def test_non_incremental_sync_preserves_date_window_without_watermark(
    database: LunchMoneyDatabase,
    client: AsyncMock,
) -> None:
    """Keep the existing date-window query and avoid watermark writes by default."""
    start_date = datetime.date(2026, 6, 1)
    end_date = datetime.date(2026, 7, 1)

    await sync_database(
        db=database,
        client=cast(LunchMoneyApp, client),
        start_date=start_date,
        end_date=end_date,
    )

    client.refresh_transactions.assert_awaited_once_with(
        start_date=start_date,
        end_date=end_date,
        cache=False,
    )
    assert (await database.get_sync_metadata("transactions")) is not None


@pytest.mark.asyncio
async def test_transaction_reconciliation_prunes_only_authoritative_window(
    database: LunchMoneyDatabase,
) -> None:
    """Remove missing in-window transactions while preserving older history."""
    from database.factories import (
        category_object,
        manual_account_object,
        plaid_account_object,
        transaction_object,
        user_object,
    )

    retained = Transaction.from_api(transaction_object(transaction_id=100, tag_ids=[]))
    missing = Transaction.from_api(transaction_object(transaction_id=101, tag_ids=[]))
    historical = Transaction.from_api(
        transaction_object(transaction_id=102, tag_ids=[])
    )
    historical.var_date = datetime.date(2025, 12, 1)
    await database.upsert_many_without_reload(
        [
            User.from_api(user_object()),
            PlaidAccount.from_api(plaid_account_object()),
            ManualAccount.from_api(manual_account_object()),
            Category.from_api(category_object()),
            retained,
            missing,
            historical,
        ]
    )

    await database.reconcile_sync_projection(
        authoritative_ids={Transaction: {retained.id}},
        transaction_window=(datetime.date(2026, 1, 1), datetime.date(2026, 1, 1)),
    )

    assert await database.get(Transaction, retained.id) is not None
    assert await database.get(Transaction, missing.id) is None
    assert await database.get(Transaction, historical.id) is not None


@pytest.mark.asyncio
async def test_incremental_reconciliation_never_prunes_transactions(
    database: LunchMoneyDatabase,
) -> None:
    """Treat updated-since results as changes rather than a complete snapshot."""
    from database.factories import transaction_object

    transaction = Transaction.from_api(
        transaction_object(transaction_id=100, tag_ids=[])
    )
    transaction.category_id = None
    transaction.plaid_account_id = None
    await database.upsert_many_without_reload([transaction])

    await database.reconcile_sync_projection(
        authoritative_ids={Transaction: set()},
        transaction_window=None,
    )

    assert await database.get(Transaction, transaction.id) is not None


@pytest.mark.asyncio
async def test_metadata_reconciliation_removes_deleted_tags_and_recurring_items(
    database: LunchMoneyDatabase,
) -> None:
    """Remove stale rows from complete metadata snapshots, including empty ones."""
    from database.factories import tag_object

    await database.upsert_many_without_reload(
        [
            Tag.from_api(tag_object(tag_id=1)),
            Tag.from_api(tag_object(tag_id=2)),
            RecurringItem(id=10, payload={"payee": "retained"}),
            RecurringItem(id=11, payload={"payee": "deleted"}),
        ]
    )

    await database.reconcile_sync_projection(
        authoritative_ids={Tag: {1}, RecurringItem: {10}},
    )

    assert [tag.id for tag in await database.list(Tag)] == [1]
    assert [item.id for item in await database.list(RecurringItem)] == [10]


@pytest.mark.asyncio
async def test_bounded_recurring_reconciliation_preserves_absent_definitions(
    database: LunchMoneyDatabase,
) -> None:
    """Do not globally delete recurring definitions absent from a date window."""
    retained = RecurringItem(id=10, payload={"payee": "in window"})
    out_of_window = RecurringItem(id=11, payload={"payee": "outside window"})
    await database.upsert_many_without_reload([retained, out_of_window])

    await database.reconcile_sync_projection(
        records=[retained],
        authoritative_ids={},
    )

    assert [item.id for item in await database.list(RecurringItem)] == [10, 11]


@pytest.mark.asyncio
async def test_sync_projection_prefetch_query_count_does_not_scale_per_record(
    database: LunchMoneyDatabase,
) -> None:
    """Load existing transaction graphs in a batch instead of once per record."""
    from database.factories import transaction_object

    transactions = []
    for transaction_id in range(100, 120):
        transaction = Transaction.from_api(
            transaction_object(transaction_id=transaction_id, tag_ids=[])
        )
        transaction.category_id = None
        transaction.plaid_account_id = None
        transactions.append(transaction)
    await database.upsert_many_without_reload(transactions)
    select_count = 0

    def count_selects(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        """Count SQL SELECT statements issued during batch reconciliation."""
        del connection, cursor, parameters, context, executemany
        nonlocal select_count
        if statement.lstrip().upper().startswith("SELECT"):
            select_count += 1

    event.listen(database.engine.sync_engine, "before_cursor_execute", count_selects)
    try:
        await database.reconcile_sync_projection(
            records=transactions,
            authoritative_ids={Transaction: {item.id for item in transactions}},
        )
    finally:
        event.remove(
            database.engine.sync_engine, "before_cursor_execute", count_selects
        )

    assert select_count < len(transactions)


@pytest.mark.asyncio
async def test_projection_cache_and_watermark_roll_back_together(
    database: LunchMoneyDatabase,
) -> None:
    """Keep cache, normalized rows, and watermarks on one transaction boundary."""
    item = RecurringItem(id=99, payload={"payee": "atomic"})

    def fail_watermark_insert(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        """Fail after projection and cache statements have been staged."""
        del connection, cursor, parameters, context, executemany
        if statement.lstrip().upper().startswith("INSERT INTO SYNC_METADATA"):
            raise RuntimeError("synthetic watermark failure")

    event.listen(
        database.engine.sync_engine, "before_cursor_execute", fail_watermark_insert
    )
    try:
        with pytest.raises(RuntimeError, match="synthetic watermark failure"):
            await database.reconcile_sync_projection(
                records=[item],
                authoritative_ids={},
                cached_responses={"recurring:latest": {"items": []}},
                sync_metadata=[
                    SyncMetadata(
                        domain="metadata",
                        last_synced_at=datetime.datetime.now(datetime.timezone.utc),
                    )
                ],
            )
    finally:
        event.remove(
            database.engine.sync_engine,
            "before_cursor_execute",
            fail_watermark_insert,
        )

    assert await database.get(RecurringItem, item.id) is None
    assert await database.get_cached_response("recurring:latest") is None
    assert await database.get_sync_metadata("metadata") is None
