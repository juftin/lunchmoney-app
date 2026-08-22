# Sprint 0: Incremental ETL and Stateless Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested opt-in incremental transaction synchronization mode and a shared in-memory SQLite mode without changing default sync behavior.

**Architecture:** `Settings` resolves the persistence mode and overlap default. `LunchMoneyDatabase` owns ephemeral schema initialization, while the sync module reads and writes a transaction watermark around its existing upstream refresh and graph upsert. The REST router and MCP tool only forward the sync options to the service layer.

**Tech Stack:** Python 3.13, Pydantic Settings, SQLModel, SQLAlchemy asyncio, Alembic, FastAPI, FastMCP, pytest, Ruff, ty, go-task, uv.

## Global Constraints

- Preserve `incremental=False` as the default 30-day rolling transaction sync.
- Use `STATELESS=true` only when no explicit database URL is supplied.
- Use a shared SQLite in-memory URI with SQLAlchemy `StaticPool` for stateless mode.
- Store UTC, timezone-aware watermarks in the `sync_metadata` table.
- Only write the `transactions` watermark after all sync refreshes and the database upsert succeed.
- Keep all business rules in `app/sync.py` and `services/sync.py`; routers and MCP tools remain delegators.
- Use synthetic test data only.
- Run checks through `task`, not direct underlying tooling.

---

### Task 1: Settings and stateless database lifecycle

**Files:**

- Modify: `src/lunchmoney_app/config.py`
- Modify: `src/lunchmoney_app/database/backend.py`
- Modify: `src/lunchmoney_app/database/__init__.py`
- Modify: `tests/test_config.py`
- Modify: `tests/database/test_backend.py`

**Interfaces:**

- Produces: `IN_MEMORY_DATABASE_URL: str`, `Settings.stateless: bool`, `Settings.sync_safety_margin_minutes: int`, `resolve_database_url(database_url: str | None = None) -> str`, and `LunchMoneyDatabase.create_tables() -> None`.
- Consumes: the existing `LUNCHMONEY_DATABASE_URL` precedence and SQLModel metadata.

- [ ] **Step 1: Write failing settings and lifecycle tests**

Add tests that assert:

```python
def test_stateless_settings_select_shared_memory_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STATELESS", "true")
    monkeypatch.delenv("LUNCHMONEY_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    assert resolve_database_url() == IN_MEMORY_DATABASE_URL

@pytest.mark.asyncio
async def test_stateless_database_create_tables_persists_across_sessions() -> None:
    async with LunchMoneyDatabase(IN_MEMORY_DATABASE_URL) as database:
        await database.create_tables()
        await database.upsert(User(...))
        assert (await database.get(User, 1)) is not None
```

Also test the default `False`/`5` values and that an explicit URL and
`LUNCHMONEY_DATABASE_URL` override stateless mode.

- [ ] **Step 2: Verify RED**

Run: `task test -- tests/test_config.py tests/database/test_backend.py`

Expected: failures because the stateless settings, memory URL, and
`create_tables()` do not exist.

- [ ] **Step 3: Implement the minimal configuration and lifecycle behavior**

Add the two Pydantic settings with the documented aliases. Define the shared
URI as `sqlite+aiosqlite:///file:memdb?mode=memory&cache=shared&uri=true`.
Resolve an explicit argument first, then an environment URL, then this URI when
`get_settings().stateless` is true, and finally the persistent default. Create
the engine with `poolclass=StaticPool` only for that URI, retain SQLite foreign
key activation, and add `create_tables()` using
`await connection.run_sync(SQLModel.metadata.create_all)`.

- [ ] **Step 4: Verify GREEN**

Run: `task test -- tests/test_config.py tests/database/test_backend.py`

Expected: the new settings and stateless lifecycle tests pass alongside the
existing database tests.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/lunchmoney_app/config.py src/lunchmoney_app/database tests/test_config.py tests/database/test_backend.py
git commit -m "✨ Add stateless database configuration"
```

### Task 2: Sync metadata model and migration

**Files:**

- Create: `src/lunchmoney_app/database/models/sync.py`
- Modify: `src/lunchmoney_app/database/models/__init__.py`
- Modify: `src/lunchmoney_app/database/__init__.py`
- Modify: `src/lunchmoney_app/database/backend.py`
- Modify: `alembic/env.py`
- Create: `alembic/versions/0002_add_sync_metadata_table.py`
- Modify: `tests/database/test_migrations.py`
- Create: `tests/test_incremental_sync.py`

**Interfaces:**

- Produces: `SyncMetadata(domain: str, last_synced_at: datetime)` and database
  access methods `get_sync_metadata(domain: str) -> SyncMetadata | None` and
  `upsert_sync_metadata(metadata: SyncMetadata) -> SyncMetadata`.
- Consumes: `SQLModel.metadata`, async sessions, and the existing Alembic
  migration environment.

- [ ] **Step 1: Write failing schema, migration, and metadata tests**

Create tests that upgrade a fresh database to `head`, inspect its tables for
`sync_metadata`, then persist and reload a watermark:

```python
@pytest.mark.asyncio
async def test_sync_metadata_is_upserted_by_domain(database: LunchMoneyDatabase) -> None:
    timestamp = datetime.datetime(2026, 7, 28, tzinfo=datetime.UTC)
    stored = await database.upsert_sync_metadata(
        SyncMetadata(domain="transactions", last_synced_at=timestamp)
    )
    assert stored.last_synced_at == timestamp
    assert (await database.get_sync_metadata("transactions")) == stored
```

- [ ] **Step 2: Verify RED**

Run: `task test -- tests/database/test_migrations.py tests/test_incremental_sync.py`

Expected: collection fails because `SyncMetadata` and its metadata methods are
absent.

- [ ] **Step 3: Implement the metadata boundary**

Define `SyncMetadata` as a SQLModel table with `domain` as its string primary
key and `last_synced_at` as a non-null timezone-aware datetime. Register it in
both public model exports and Alembic metadata imports. Add the two focused
database methods without adding `SyncMetadata` to the existing API-record
convenience set. Write migration `0002`, with `down_revision = "0001"`, that
creates and drops the two-column table.

- [ ] **Step 4: Verify GREEN**

Run: `task test -- tests/database/test_migrations.py tests/test_incremental_sync.py`

Expected: the real migration creates the table and the metadata round trip
passes.

- [ ] **Step 5: Commit Task 2**

```bash
git add alembic src/lunchmoney_app/database tests/database/test_migrations.py tests/test_incremental_sync.py
git commit -m "✨ Add incremental sync metadata"
```

### Task 3: Incremental synchronization policy

**Files:**

- Modify: `src/lunchmoney_app/app/sync.py`
- Modify: `src/lunchmoney_app/services/sync.py`
- Modify: `tests/test_incremental_sync.py`
- Modify: `tests/test_app.py`

**Interfaces:**

- Produces: `sync_database(..., incremental: bool = False, safety_margin_minutes: int | None = None) -> SyncSummary`, `execute_sync(...) -> SyncResponse`, and `execute_mcp_sync(...) -> SyncResult` with the same parameters.
- Consumes: `LunchMoneyDatabase.get_sync_metadata`,
  `LunchMoneyDatabase.upsert_sync_metadata`, `Settings.sync_safety_margin_minutes`, and
  `LunchMoneyApp.refresh_transactions(updated_since=...)`.

- [ ] **Step 1: Write failing policy tests**

Use an async fake client to assert these behaviors:

```python
@pytest.mark.asyncio
async def test_incremental_sync_subtracts_requested_safety_margin(...) -> None:
    watermark = datetime.datetime(2026, 7, 28, 12, 0, tzinfo=datetime.UTC)
    await database.upsert_sync_metadata(SyncMetadata("transactions", watermark))
    await sync_database(..., incremental=True, safety_margin_minutes=7)
    client.refresh_transactions.assert_awaited_once_with(
        updated_since=watermark - datetime.timedelta(minutes=7), cache=False
    )

@pytest.mark.asyncio
async def test_failed_incremental_sync_does_not_advance_watermark(...) -> None:
    client.refresh_transactions.side_effect = RuntimeError("synthetic upstream failure")
    with pytest.raises(RuntimeError, match="synthetic upstream failure"):
        await sync_database(..., incremental=True)
    assert await database.get_sync_metadata("transactions") is None
```

Also cover no-watermark fallback to the existing date range, the configured
margin when no request override is given, successful watermark creation after
the upsert, and unchanged non-incremental behavior.

- [ ] **Step 2: Verify RED**

Run: `task test -- tests/test_incremental_sync.py tests/test_app.py`

Expected: failures because sync accepts neither incremental parameters nor
reads/writes a watermark.

- [ ] **Step 3: Implement incremental policy in the application and service layers**

Add the optional parameters to all three sync functions. For an incremental
sync with a transaction watermark, call `refresh_transactions` using only
`updated_since=watermark - timedelta(minutes=resolved_margin)` and
`cache=False`; otherwise preserve the current `start_date`, `end_date`, and
`cache=False` call. Capture `datetime.now(datetime.UTC)` before refreshes and
write the transaction watermark after `db.upsert_many(records)` completes.
Resolve an omitted margin from settings and propagate service arguments without
placing policy in transport code.

- [ ] **Step 4: Verify GREEN**

Run: `task test -- tests/test_incremental_sync.py tests/test_app.py`

Expected: incremental overlap, fallback, success, failure, and existing default
sync tests all pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/lunchmoney_app/app/sync.py src/lunchmoney_app/services/sync.py tests/test_incremental_sync.py tests/test_app.py
git commit -m "✨ Add opt-in incremental transaction sync"
```

### Task 4: REST/MCP transport exposure and documentation

**Files:**

- Modify: `src/lunchmoney_app/app/routers/sync.py`
- Modify: `src/lunchmoney_app/mcp/tools/sync.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_mcp.py`
- Modify: `docs/maintainers/CHECKLIST.md`
- Modify: `docs/maintainers/INCREMENTAL_ETL.md`

**Interfaces:**

- Produces: `POST /api/sync?incremental=true&safety_margin_minutes=...` and
  `sync_data(incremental=True, safety_margin_minutes=...)`.
- Consumes: service-layer sync functions from Task 3.

- [ ] **Step 1: Write failing transport tests**

Patch the service functions and assert exact delegated keyword arguments:

```python
response = client.post("/sync?days=14&incremental=true&safety_margin_minutes=9")
assert response.status_code == 200
mock_execute_sync.assert_awaited_once_with(
    db=ANY, client=ANY, days=14, incremental=True, safety_margin_minutes=9
)
```

Invoke the registered MCP tool through FastMCP's test interface and assert it
passes the same keyword arguments to `execute_mcp_sync`.

- [ ] **Step 2: Verify RED**

Run: `task test -- tests/test_app.py tests/test_mcp.py`

Expected: the transport functions reject the new parameters or omit them when
delegating.

- [ ] **Step 3: Implement pure delegation and mark documented work complete**

Add the two parameters, their type hints, and NumPy-style docstrings to the
FastAPI route and MCP tool. Forward them unchanged to the services. Update the
incremental ETL document to state that the implemented domain is
`transactions`, and mark every Sprint 0 checklist item complete only after the
verification in Step 4 succeeds.

- [ ] **Step 4: Verify full Sprint 0 quality gate**

Run:

```bash
task fix
task lint
task check
task test
```

Expected: all commands exit with code `0`; inspect the formatter/linter diff to
ensure it is limited to Sprint 0 files before staging.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/lunchmoney_app/app/routers/sync.py src/lunchmoney_app/mcp/tools/sync.py tests/test_app.py tests/test_mcp.py docs/maintainers/CHECKLIST.md docs/maintainers/INCREMENTAL_ETL.md
git commit -m "✨ Expose incremental synchronization controls"
```

## Plan self-review

- Sprint 0 configuration, stateless database initialization, schema migration,
  incremental filtering, transport integration, documentation, and tests map to
  Tasks 1 through 4.
- The plan has no unresolved implementation placeholders.
- Each later interface is produced by an earlier task, and every behavior has a
  failing-test and passing-test checkpoint.
