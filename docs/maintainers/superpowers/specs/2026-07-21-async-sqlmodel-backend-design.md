# Async SQLModel Backend Design

## Goal

Add a standalone, fully normalized SQL persistence backend for Lunch Money data. The backend uses native SQLModel records, SQLAlchemy async engines, Alembic migrations, persistent async SQLite by default, and async Postgres when configured. It does not modify or integrate with `LunchMoneyApp` or `LunchableData`.

## Scope

The first version provides persistence only:

- normalized SQLModel tables;
- async engine and session management;
- relationship-aware CRUD convenience methods;
- direct access to native SQLModel sessions and queries;
- conversion between SQLModel records and the generated Lunch Money Pydantic API models;
- Alembic migrations for SQLite and Postgres.

It does not provide financial queries, reporting, aggregation, application cache hydration, synchronization orchestration, or multi-account tenancy.

Each database stores data for one Lunch Money account.

## Architecture

`LunchMoneyApp` and `LunchableData` remain unchanged. The persistence backend lives in a separate package:

```text
src/lunchmoney_app/
├── app.py
└── database/
    ├── __init__.py
    ├── backend.py
    └── models/
        ├── __init__.py
        ├── accounts.py
        ├── categories.py
        ├── tags.py
        ├── transactions.py
        └── users.py

alembic/
├── env.py
├── script.py.mako
└── versions/
    └── <revision>_initial_schema.py
```

SQLModel table classes are the persistence layer's public data types. They do not inherit from the generated Lunch Money classes. Instead, each record type explicitly defines its database columns and relationships and provides:

```python
@classmethod
def from_api(cls, model: ApiModel) -> Self: ...

def to_api(self) -> ApiModel: ...
```

`from_api()` converts nested API objects and ID lists into a normalized SQLModel graph. `to_api()` reconstructs the corresponding generated Pydantic model. Conversion is optional; callers may use SQLModel records exclusively.

## Database Configuration

The default URL is:

```text
sqlite+aiosqlite:///lunchmoney.db
```

Callers may supply another SQLAlchemy async URL, including:

```text
postgresql+asyncpg://user:password@host/database
```

The constructor argument takes precedence over the `LUNCHMONEY_DATABASE_URL` environment variable, which takes precedence over the default SQLite URL.

The runtime dependencies are:

- `sqlmodel`;
- `sqlalchemy`;
- `aiosqlite`;
- `asyncpg`;
- `alembic`.

Dependencies are managed with `uv` and committed in `pyproject.toml` and `uv.lock`.

## SQLModel Schema

All Lunch Money API scalar fields become explicit typed columns. Enums are stored as strings for portable SQLite and Postgres migrations. Monetary values such as amounts and balances use `Numeric(20, 10)` and Python `Decimal`; conversion back to API models produces strings where required by the generated schema.

### Users

The `User` table contains every `UserObject` field. Its Lunch Money `id` is the primary key.

### Accounts

`PlaidAccount` and `ManualAccount` are separate tables because their schemas and lifecycle differ. Every field from `PlaidAccountObject` and `ManualAccountObject` is mapped to a column.

`ManualAccount.custom_metadata` remains a JSON column because the API intentionally defines it as an arbitrary mapping rather than a structured model.

### Categories

`Category` represents both `CategoryObject` and `ChildCategoryObject`. It is self-referencing:

- `id` is the Lunch Money category ID and primary key;
- `group_id` is a nullable foreign key to `categories.id`;
- `parent` and `children` are SQLModel relationships.

`Category.from_api()` recursively converts a parent category and its children. `Category.to_api()` reconstructs `CategoryObject` for parent records and `ChildCategoryObject` for child records. The record exposes an explicit category-kind discriminator where necessary to make that conversion deterministic.

### Tags

`Tag` contains every `TagObject` field. Its Lunch Money `id` is the primary key.

### Transactions

`Transaction` covers the union of fields from `TransactionObject` and `ChildTransactionObject`. It stores both top-level and nested transactions in one table. The existing `split_parent_id` and `group_parent_id` values are self-referencing foreign keys and expose typed parent/child relationships.

The table includes a discriminator that records whether a row originated from a top-level `TransactionObject` or a nested `ChildTransactionObject`, allowing deterministic `to_api()` conversion.

`plaid_metadata` and `custom_metadata` remain JSON columns because they are arbitrary API mappings.

### Transaction Tags

`TransactionTagLink` is a SQLModel link table between `Transaction` and `Tag`. It replaces the API model's `tag_ids` list and uses a composite primary key of transaction ID and tag ID.

### Transaction Attachments

`TransactionAttachment` contains every `TransactionAttachmentObject` field and belongs to one transaction. Because the Lunch Money attachment ID is optional, the table uses an internal generated primary key while retaining the nullable API attachment ID in a separate indexed column.

Attachments without API IDs are matched by graph ownership during a read and are replaced atomically during an update.

## Referential Integrity

Foreign keys are enforced. Transactions must not refer to absent accounts, categories, tags, or parent transactions. Owned relationship rows use database cascades where deletion semantics are unambiguous:

- deleting a transaction deletes its tag links and attachments;
- deleting a parent category deletes its owned child categories;
- deleting a parent transaction deletes nested split or group children owned by that parent;
- deleting referenced accounts, categories, or tags is restricted while transactions depend on them.

Persistence batches order dependencies as user, accounts, categories, tags, and transactions. Any missing dependency or constraint violation aborts the entire transaction and propagates the SQLAlchemy integrity error.

## `LunchMoneyDatabase`

`LunchMoneyDatabase` is a thin convenience layer around native SQLModel and SQLAlchemy. It centralizes:

- the default database URL;
- async engine creation;
- `async_sessionmaker` configuration;
- commit and rollback boundaries;
- relationship-aware upsert and delete behavior;
- eager-loading rules required for complete record graphs and `to_api()`;
- deterministic engine disposal.

It does not provide a custom query language or hide SQLModel. It exposes:

- `engine`;
- `session_factory`;
- an async `session()` context manager yielding SQLModel's async session;
- async context-manager support for deterministic disposal.

Native access remains available:

```python
async with db.session() as session:
    result = await session.exec(
        select(Transaction).where(Transaction.var_date >= start_date)
    )
    transactions = result.all()
```

The convenience persistence interface is:

```python
record = Transaction.from_api(api_transaction)
await db.upsert(record)
await db.upsert_many(records)

stored = await db.get(Transaction, transaction_id)
records = await db.list(Transaction)
deleted = await db.delete(Transaction, transaction_id)

api_transaction = stored.to_api()
```

`upsert()` accepts a supported SQLModel record and returns its fully loaded persisted record. `upsert_many()` accepts homogeneous or mixed supported records, orders dependencies, and commits atomically. Updating a category or transaction replaces its owned nested relationships atomically so removed children, links, and attachments do not remain stale.

`get()` and `list()` return SQLModel records with the relationships required by the record type eagerly loaded. `get()` returns `None` for an absent primary key. `delete()` returns whether a row existed.

Unsupported record classes raise `TypeError`. Driver, connection, migration, and constraint errors retain their native SQLAlchemy exception types.

## Session and Transaction Semantics

Each convenience CRUD operation creates one async session and one transaction. Successful operations commit once. Exceptions trigger rollback and are re-raised. Returned records are usable after commit because sessions are configured with `expire_on_commit=False` and required relationships are loaded before the session closes.

Callers using `db.session()` own their SQLModel operations and explicit commit behavior. The context manager guarantees session closure but does not silently commit arbitrary native operations.

## Alembic

Alembic is the production schema-management mechanism. `LunchMoneyDatabase` never calls `SQLModel.metadata.create_all()` implicitly.

Alembic's target metadata is `SQLModel.metadata`. The environment supports async migration execution and obtains its database URL from Alembic configuration, then `LUNCHMONEY_DATABASE_URL`, and finally the persistent async SQLite default.

The initial migration explicitly creates all tables, indexes, foreign keys, uniqueness constraints, and cascade rules. The same revision must upgrade and downgrade on SQLite and Postgres.

Tests may use metadata creation for narrow model tests, but persistence integration tests run the real Alembic migration to verify deployable schema behavior.

## Testing

SQLite integration tests use a temporary persistent database file. They apply `alembic upgrade head` before testing persistence behavior.

Postgres integration tests run when `TEST_POSTGRES_URL` is configured. They apply the same migration and persistence contract and are skipped when Postgres is unavailable.

Coverage includes:

- every record's `from_api()` and `to_api()` round trip;
- every scalar column and nullable field;
- decimal and enum conversion;
- category parent-child graphs;
- transaction parent-child graphs;
- transaction-tag links;
- attachments with and without Lunch Money IDs;
- JSON metadata;
- scalar and graph upserts;
- atomic relationship replacement;
- mixed dependency-ordered batches;
- get, list, and delete behavior;
- cascade and restrict rules;
- rollback on constraint failure;
- native async SQLModel session access;
- Alembic upgrade and downgrade on supported databases.

All existing `LunchMoneyApp` tests must continue to pass unchanged.

## Documentation

The README will document:

- dependency and driver behavior;
- default SQLite storage location;
- Postgres URL configuration;
- Alembic upgrade commands;
- native SQLModel usage;
- `LunchMoneyDatabase` convenience usage;
- `from_api()` and `to_api()` conversion;
- the single-account database constraint.
