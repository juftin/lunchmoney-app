# Async SQLModel Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate, fully normalized async SQLModel persistence backend with persistent SQLite defaults, async Postgres support, API-model conversion, native session access, and Alembic migrations.

**Architecture:** Native SQLModel table records form the public persistence boundary. `LunchMoneyDatabase` is a thin async engine/session and graph-CRUD convenience layer, while callers retain direct access to SQLModel `AsyncSession`; generated Lunch Money models are translated explicitly through `from_api()` and `to_api()`.

**Tech Stack:** Python 3.13, SQLModel, SQLAlchemy asyncio, aiosqlite, asyncpg, Alembic, pytest, pytest-asyncio, uv, Ruff, ty.

## Global Constraints

- Keep `LunchMoneyApp` and `LunchableData` unchanged.
- Scope each database to one Lunch Money account.
- Default to `sqlite+aiosqlite:///lunchmoney.db`.
- Resolve URLs in this order: constructor argument, `LUNCHMONEY_DATABASE_URL`, default SQLite URL.
- Support `postgresql+asyncpg://...` URLs.
- Use explicit SQLModel table classes; do not inherit generated Lunch Money API classes.
- Store monetary values as `Decimal` in `Numeric(20, 10)` columns.
- Store enums as strings and arbitrary metadata mappings as JSON.
- Enforce foreign keys and atomic graph replacement.
- Use Alembic for production schema management; never call `create_all()` implicitly.
- Return native SQLModel records from persistence methods; API conversion is explicit through `from_api()` and `to_api()`.
- Preserve native SQLAlchemy exceptions.
- Manage dependencies with `uv`, and run project workflows with `uv run` because no Taskfile exists.

---

### Task 1: Dependencies and async database configuration

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/lunchmoney_mcp/database/__init__.py`
- Create: `src/lunchmoney_mcp/database/backend.py`
- Create: `tests/database/test_backend.py`

**Interfaces:**
- Produces: `DEFAULT_DATABASE_URL: str`, `resolve_database_url(database_url: str | None = None) -> str`, and `LunchMoneyDatabase` with `engine`, `session_factory`, `session()`, async context-manager support, and `dispose()`.

- [ ] **Step 1: Add the runtime dependencies using uv**

Run:

```bash
uv add sqlmodel sqlalchemy aiosqlite asyncpg alembic
```

Expected: `pyproject.toml` and `uv.lock` include all five runtime dependencies while retaining existing dependencies.

- [ ] **Step 2: Write failing configuration and session tests**

Create `tests/database/test_backend.py` with tests that:

```python
"""Tests for async database configuration and lifecycle."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from lunchmoney_mcp.database import DEFAULT_DATABASE_URL, LunchMoneyDatabase
from lunchmoney_mcp.database.backend import resolve_database_url


def test_default_database_url_is_persistent_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use the persistent SQLite URL when no override exists."""
    monkeypatch.delenv("LUNCHMONEY_DATABASE_URL", raising=False)
    assert resolve_database_url() == DEFAULT_DATABASE_URL
    assert DEFAULT_DATABASE_URL == "sqlite+aiosqlite:///lunchmoney.db"


def test_explicit_database_url_precedes_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prefer an explicit database URL over the environment."""
    monkeypatch.setenv("LUNCHMONEY_DATABASE_URL", "sqlite+aiosqlite:///env.db")
    assert resolve_database_url("sqlite+aiosqlite:///explicit.db").endswith("explicit.db")


@pytest.mark.asyncio
async def test_database_exposes_native_async_session(tmp_path: Path) -> None:
    """Yield SQLModel's native async session and dispose cleanly."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'database.db'}"
    async with LunchMoneyDatabase(url) as database:
        assert isinstance(database.engine, AsyncEngine)
        async with database.session() as session:
            assert isinstance(session, AsyncSession)
```

- [ ] **Step 3: Run the tests to verify RED**

Run: `uv run pytest tests/database/test_backend.py -v`

Expected: collection fails because `lunchmoney_mcp.database` does not exist.

- [ ] **Step 4: Implement the minimal backend lifecycle**

Implement `backend.py` using `create_async_engine`, `async_sessionmaker(..., class_=AsyncSession, expire_on_commit=False)`, `@asynccontextmanager` for `session()`, and `await engine.dispose()` for cleanup. Export the public names from `database/__init__.py`. The session context closes sessions but does not commit native caller operations.

- [ ] **Step 5: Verify GREEN**

Run: `uv run pytest tests/database/test_backend.py -v`

Expected: all Task 1 tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add pyproject.toml uv.lock src/lunchmoney_mcp/database tests/database/test_backend.py
git commit -m "✨ Add async SQLModel database lifecycle"
```

### Task 2: Scalar SQLModel records and API conversions

**Files:**
- Create: `src/lunchmoney_mcp/database/models/__init__.py`
- Create: `src/lunchmoney_mcp/database/models/users.py`
- Create: `src/lunchmoney_mcp/database/models/accounts.py`
- Create: `src/lunchmoney_mcp/database/models/tags.py`
- Create: `tests/database/factories.py`
- Create: `tests/database/test_scalar_models.py`

**Interfaces:**
- Produces: `User`, `PlaidAccount`, `ManualAccount`, and `Tag`, each with `from_api()` and `to_api()`.
- Consumes: generated `UserObject`, `PlaidAccountObject`, `ManualAccountObject`, and `TagObject`.

- [ ] **Step 1: Write complete synthetic API-model factories**

In `tests/database/factories.py`, construct every required generated field using deterministic synthetic values. Provide:

```python
def user_object() -> UserObject: ...
def plaid_account_object() -> PlaidAccountObject: ...
def manual_account_object() -> ManualAccountObject: ...
def tag_object(tag_id: int = 1) -> TagObject: ...
```

Use `model_validate()` with all required fields discovered from `model_fields`; use UTC datetimes, `date(2026, 1, 1)`, non-secret fake IDs, and enum values selected from each installed enum's first valid member.

- [ ] **Step 2: Write failing round-trip tests**

Create parametrized tests asserting that each `Record.from_api(api).to_api().model_dump(mode="json")` exactly equals `api.model_dump(mode="json")`. Also assert monetary record attributes are `Decimal`, enums are stored as strings, and manual-account metadata remains a dictionary.

- [ ] **Step 3: Run the tests to verify RED**

Run: `uv run pytest tests/database/test_scalar_models.py -v`

Expected: collection fails because the SQLModel record classes do not exist.

- [ ] **Step 4: Implement explicit scalar tables**

Define every API scalar field as a SQLModel column. Use `Field(sa_type=Numeric(20, 10))` for monetary values, SQLAlchemy `JSON` for custom metadata, indexed Lunch Money IDs as primary keys, and string columns for enums. Implement explicit conversion methods with NumPy-style docstrings and exact API model return types.

- [ ] **Step 5: Verify GREEN and metadata registration**

Run: `uv run pytest tests/database/test_scalar_models.py -v`

Expected: all round trips pass, and `SQLModel.metadata.tables` contains `users`, `plaid_accounts`, `manual_accounts`, and `tags`.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/lunchmoney_mcp/database/models tests/database/factories.py tests/database/test_scalar_models.py
git commit -m "✨ Add scalar Lunch Money SQLModel records"
```

### Task 3: Normalized category graphs

**Files:**
- Create: `src/lunchmoney_mcp/database/models/categories.py`
- Modify: `src/lunchmoney_mcp/database/models/__init__.py`
- Modify: `tests/database/factories.py`
- Create: `tests/database/test_categories.py`

**Interfaces:**
- Produces: `CategoryKind` string enum and self-referencing `Category` SQLModel with `parent`, `children`, `from_api()`, `to_api()`, and `to_child_api()`.

- [ ] **Step 1: Add parent and child API factories**

Add `child_category_object()` and `category_object(children: list[ChildCategoryObject] | None = None)` with every generated field populated.

- [ ] **Step 2: Write failing graph tests**

Assert that `Category.from_api(parent)` creates parent and child records, sets each child's `group_id`, preserves order, and round-trips the full API JSON. Assert that a child record converts to `ChildCategoryObject`, and SQLModel metadata contains a self foreign key from `categories.group_id` to `categories.id`.

- [ ] **Step 3: Run RED**

Run: `uv run pytest tests/database/test_categories.py -v`

Expected: import failure for `Category`.

- [ ] **Step 4: Implement the category table**

Create a single `categories` table with all fields in the union of `CategoryObject` and `ChildCategoryObject`, plus a string `kind` discriminator. Define self relationships with explicit `remote_side`, `back_populates`, and delete-orphan cascade semantics for owned children.

- [ ] **Step 5: Verify GREEN**

Run: `uv run pytest tests/database/test_categories.py -v`

Expected: category graph and conversion tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/lunchmoney_mcp/database/models tests/database
git commit -m "✨ Add normalized category records"
```

### Task 4: Normalized transaction graphs

**Files:**
- Create: `src/lunchmoney_mcp/database/models/transactions.py`
- Modify: `src/lunchmoney_mcp/database/models/__init__.py`
- Modify: `tests/database/factories.py`
- Create: `tests/database/test_transactions.py`

**Interfaces:**
- Produces: `TransactionKind`, `Transaction`, `TransactionTagLink`, and `TransactionAttachment` with native relationships and API conversion.
- Consumes: `Tag`, account tables, `Category`, `TransactionObject`, `ChildTransactionObject`, and `TransactionAttachmentObject`.

- [ ] **Step 1: Add full transaction factories**

Add factories for attachments with and without API IDs, child transactions, and parent transactions. Populate every generated field, including metadata, tag IDs, files, split/group IDs, and optional fields.

- [ ] **Step 2: Write failing normalized graph tests**

Assert:

```python
record = Transaction.from_api(api_transaction, tags=[Tag.from_api(tag)])
assert record.amount == Decimal(api_transaction.amount)
assert [tag.id for tag in record.tags] == api_transaction.tag_ids
assert [attachment.api_id for attachment in record.attachments] == [file.id for file in api_transaction.files or []]
assert record.to_api().model_dump(mode="json") == api_transaction.model_dump(mode="json")
```

Also test child transaction round trips, self-parent relationships, link-table composite keys, JSON metadata, and internal attachment keys when API IDs are absent.

- [ ] **Step 3: Run RED**

Run: `uv run pytest tests/database/test_transactions.py -v`

Expected: import failure for transaction records.

- [ ] **Step 4: Implement transaction tables and relationships**

Map the union of all parent and child fields. Use a discriminator for deterministic conversion, `Numeric(20, 10)` for amount and `to_base`, self foreign keys for split/group parents, a composite transaction-tag link table, and owned attachment rows with generated integer primary keys and nullable indexed `api_id`. Define cascades for links, attachments, and owned nested transactions.

- [ ] **Step 5: Verify GREEN**

Run: `uv run pytest tests/database/test_transactions.py -v`

Expected: all transaction graph and conversion tests pass.

- [ ] **Step 6: Commit Task 4**

```bash
git add src/lunchmoney_mcp/database/models tests/database
git commit -m "✨ Add normalized transaction records"
```

### Task 5: Relationship-aware async persistence

**Files:**
- Modify: `src/lunchmoney_mcp/database/backend.py`
- Modify: `src/lunchmoney_mcp/database/__init__.py`
- Create: `tests/database/conftest.py`
- Create: `tests/database/test_persistence.py`

**Interfaces:**
- Produces:

```python
async def upsert[RecordT: SQLModel](self, record: RecordT) -> RecordT: ...
async def upsert_many[RecordT: SQLModel](self, records: Iterable[RecordT]) -> list[RecordT]: ...
async def get[RecordT: SQLModel](self, model: type[RecordT], primary_key: int) -> RecordT | None: ...
async def list[RecordT: SQLModel](self, model: type[RecordT]) -> list[RecordT]: ...
async def delete[RecordT: SQLModel](self, model: type[RecordT], primary_key: int) -> bool: ...
```

- [ ] **Step 1: Add a migrated temporary SQLite fixture**

Create an async `database` fixture using a temporary persistent SQLite URL. For Task 5, create registered SQLModel metadata explicitly; Task 6 replaces the integration setup with Alembic migration execution. Enable SQLite foreign keys on every connection with an engine event listener.

- [ ] **Step 2: Write failing persistence contract tests**

Cover scalar upsert/update, graph upsert, mixed dependency-ordered `upsert_many`, get/list eager relationships, delete results, attachment and link replacement, cascade deletion, restricted deletion, unsupported model `TypeError`, rollback after `IntegrityError`, and direct `session.exec(select(...))` access.

- [ ] **Step 3: Run RED**

Run: `uv run pytest tests/database/test_persistence.py -v`

Expected: failures because CRUD methods do not exist.

- [ ] **Step 4: Implement supported-record dispatch and graph persistence**

Use explicit supported-type dispatch rather than reflection. For scalar records, select by primary key then call `sqlmodel_update()` or add. For graph records, load existing relationships, update scalars, and replace owned collections inside the same transaction. Sort mixed batches by user, accounts, categories, tags, and transactions. Use `selectinload` options per model before returning detached records.

- [ ] **Step 5: Verify GREEN**

Run: `uv run pytest tests/database/test_persistence.py -v`

Expected: all persistence contract tests pass with foreign keys enabled.

- [ ] **Step 6: Commit Task 5**

```bash
git add src/lunchmoney_mcp/database tests/database
git commit -m "✨ Add async SQLModel persistence operations"
```

### Task 6: Alembic async migrations and Postgres contract

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/0001_initial_schema.py`
- Modify: `tests/database/conftest.py`
- Create: `tests/database/test_migrations.py`

**Interfaces:**
- Produces: a reversible `0001` schema migration and async Alembic URL resolution consistent with `resolve_database_url()`.

- [ ] **Step 1: Write failing migration tests**

Programmatically build an Alembic `Config`, set a temporary SQLite URL, run `command.upgrade(config, "head")`, inspect all expected tables/constraints, run `command.downgrade(config, "base")`, and assert application tables are removed. Parametrize the same contract with `TEST_POSTGRES_URL` when present.

- [ ] **Step 2: Run RED**

Run: `uv run pytest tests/database/test_migrations.py -v`

Expected: failure because Alembic configuration and revision files do not exist.

- [ ] **Step 3: Implement the async Alembic environment**

Import all model modules before setting `target_metadata = SQLModel.metadata`. Resolve URLs from Alembic config, `LUNCHMONEY_DATABASE_URL`, then the SQLite default. Use Alembic's async template pattern: create the engine with `async_engine_from_config()`, call `await connection.run_sync(do_run_migrations)`, and invoke that coroutine with `asyncio.run()` from the synchronous Alembic entry point. Keep the configured `aiosqlite` or `asyncpg` URL unchanged.

- [ ] **Step 4: Write the explicit initial migration**

Create every table, `Numeric(20, 10)` column, JSON column, discriminator, index, composite key, foreign key, cascade, and restriction from the registered SQLModel metadata. Downgrade in reverse dependency order.

- [ ] **Step 5: Switch persistence fixtures to real migrations and verify GREEN**

Run:

```bash
uv run pytest tests/database/test_migrations.py tests/database/test_persistence.py -v
```

Expected: SQLite migration and persistence tests pass; Postgres tests pass when `TEST_POSTGRES_URL` is configured or report a documented skip otherwise.

- [ ] **Step 6: Commit Task 6**

```bash
git add alembic.ini alembic tests/database
git commit -m "✨ Add async SQLite and Postgres migrations"
```

### Task 7: Public API, documentation, and full verification

**Files:**
- Modify: `src/lunchmoney_mcp/database/__init__.py`
- Modify: `README.md`
- Modify: `tests/database/test_backend.py`

**Interfaces:**
- Produces documented imports for `LunchMoneyDatabase`, all record types, `DEFAULT_DATABASE_URL`, and native SQLModel usage.

- [ ] **Step 1: Write a failing public-export test**

Assert every documented symbol imports from `lunchmoney_mcp.database`, and exercise the README's SQLite example against a temporary URL without contacting Lunch Money or Postgres.

- [ ] **Step 2: Run RED**

Run: `uv run pytest tests/database/test_backend.py -v`

Expected: missing export assertions fail.

- [ ] **Step 3: Complete public exports and README**

Document dependency drivers, default SQLite location, `LUNCHMONEY_DATABASE_URL`, Postgres URLs, `alembic upgrade head`, native `AsyncSession`/`select()` usage, convenience CRUD, `from_api()`/`to_api()`, and the single-account constraint.

- [ ] **Step 4: Run project auto-fix and full verification**

Run:

```bash
uv run ruff format src tests alembic
uv run ruff check --fix src tests alembic
uv run ruff format --check src tests alembic
uv run ruff check src tests alembic
uv run ty check
uv run pytest -v
```

Expected: all commands exit zero; Postgres tests are either passing or explicitly skipped because `TEST_POSTGRES_URL` is absent.

- [ ] **Step 5: Verify requirements line by line**

Confirm `LunchMoneyApp` has no SQL imports or behavioral changes, no automatic `create_all()` exists in runtime code, SQLite is persistent by default, Postgres uses asyncpg, every generated model field is mapped, every graph round-trips, and Alembic upgrade/downgrade works.

- [ ] **Step 6: Commit Task 7**

```bash
git add README.md src/lunchmoney_mcp/database tests/database alembic alembic.ini pyproject.toml uv.lock
git commit -m "📝 Document async SQLModel persistence"
```
