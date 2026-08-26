# Database Guide

## Configuration

With no configuration, `LunchMoneyDatabase` uses the persistent SQLite file
`lunchmoney.db` in the platform-specific user data directory reported by
`platformdirs` (for example, `$XDG_DATA_HOME/lunchmoney-app` on Linux). The
`mcp` command instead defaults to database-free ephemeral operation when using
stdio; select `--persistence-mode stateful` to use the persistent default. Pass
a URL to the constructor or set `LUNCHMONEY_DATABASE_URL`; an explicit
constructor URL takes precedence.

```text
sqlite+aiosqlite:////absolute/path/to/lunchmoney.db
postgresql+asyncpg://user:password@host/database
```

Constructing `LunchMoneyDatabase` directly does not create or migrate its
schema. Stateful application runtimes (`serve`, `schedule`, and `sync`) run
Alembic migrations during startup before accessing the database, using bundled
migrations when installed so they do not require a source checkout. For direct
library use or an explicit operator migration, run:

```bash
export LUNCHMONEY_DATABASE_URL=sqlite+aiosqlite:///lunchmoney.db
uv run alembic upgrade head
```

The same command works with a `postgresql+asyncpg` URL. To reverse all
migrations, run `uv run alembic downgrade base`.

The CLI provides equivalent operator commands. `info` is safe for scripts and
redacts database passwords; `delete` uses SQLModel metadata to drop every
application table on SQLite and PostgreSQL alike, including Alembic's revision
state so a later migration recreates the schema.

```bash
lunchmoney-app db info
lunchmoney-app db migrate
lunchmoney-app db delete --yes
```

## Convenience API

All database interfaces and records are available from one package:

```python
from lunchmoney_app.database import (
    DEFAULT_DATABASE_URL,
    Category,
    CategoryKind,
    LunchMoneyDatabase,
    ManualAccount,
    PlaidAccount,
    Tag,
    Transaction,
    TransactionAttachment,
    TransactionKind,
    TransactionTagLink,
    User,
    resolve_database_url,
)
```

After applying migrations, use the convenience API for detached records and
their supported relationship graphs:

```python
from lunchmoney_app.database import LunchMoneyDatabase, User

database_url = "sqlite+aiosqlite:///lunchmoney.db"
user = User(
    id=1,
    name="Synthetic User",
    email="synthetic-user@example.invalid",
    account_id=100,
    budget_name="Synthetic Budget",
    primary_currency="usd",
    api_key_label="Synthetic key",
)

async with LunchMoneyDatabase(database_url) as database:
    await database.upsert(user)
    stored = await database.get(User, 1)
    users = await database.list(User)
    deleted = await database.delete(User, 1)
```

`upsert_many()` persists several supported records atomically and orders
dependencies for you. The convenience CRUD methods support `User`,
`PlaidAccount`, `ManualAccount`, `Category`, `Tag`, and `Transaction`; owned
attachment, tag-link, category-child, and transaction-child records are
persisted through their parent graphs.

## Native SQLModel sessions

Use `session()` when a query or transaction needs SQLModel directly. It yields
a native asynchronous `AsyncSession`; callers control commits for their own
writes.

```python
from sqlmodel import select

from lunchmoney_app.database import LunchMoneyDatabase, User

async with LunchMoneyDatabase() as database:
    async with database.session() as session:
        result = await session.exec(select(User).where(User.account_id == 100))
        users = result.all()
```

## API conversion and account scope

Each primary record supplies `from_api()` to convert its generated
`lunchmoney.models` object and `to_api()` to reconstruct that object. Category
and transaction conversions preserve their complete child graphs; pass the
available tags to `Transaction.from_api()` when resolving transaction tag
relationships.

```python
record = User.from_api(api_user)
restored_api_user = record.to_api()
```

A database is intentionally scoped to one Lunch Money budgeting account. Most
tables do not carry a tenant/account partition key, so do not mix data from
multiple Lunch Money accounts in one database. Use a separate SQLite file or
PostgreSQL database/schema and a separate `LunchMoneyDatabase` for each
account.
