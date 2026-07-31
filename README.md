# lunchmoney-mcp

Async Lunch Money persistence built on SQLModel, SQLAlchemy, and Alembic. The package
includes `aiosqlite` for SQLite and `asyncpg` for PostgreSQL; connection URLs must use
their asynchronous driver names.

## Quickstart

`LUNCHMONEY_ACCESS_TOKEN` authorizes this server to call the Lunch Money API.
For a local MCP client, set it and start the default stdio transport:

```bash
export LUNCHMONEY_ACCESS_TOKEN="your-lunch-money-token"
task run -- lunchmoney-mcp mcp --stdio
```

For a remote MCP client, choose one HTTP transport. Streamable HTTP and HTTP
use `/mcp`; SSE uses `/sse`.

```bash
task run -- lunchmoney-mcp mcp --streamable-http --host 127.0.0.1 --port 8000
# Connect at http://127.0.0.1:8000/mcp
```

The `mcp` command has no scheduler and uses ephemeral in-memory storage only.
The available transports are mutually exclusive: `--stdio` (also the default),
`--sse`, `--http`, and `--streamable-http`. `--host` and `--port` apply only to
the HTTP transports.

## Production deployment

The container image runs the combined REST and MCP ASGI application with
Gunicorn and `uvicorn-worker` on port 8000. Docker Compose uses that production
command by default:

```bash
export LUNCHMONEY_ACCESS_TOKEN="your-lunch-money-token"
task compose
```

Use `task dev` for local FastAPI development; it runs the direct Uvicorn server
with auto-reload enabled.

### Scheduled synchronization

Scheduled synchronization is a dedicated, opt-in process. It refreshes metadata
on every run and incrementally refreshes transactions; its first run uses the
configured 30-day rolling transaction window until a watermark exists.

```bash
task run -- lunchmoney-mcp schedule \
  --schedule-cron "0 * * * *" \
  --schedule-timezone "America/Denver" \
  --schedule-days 30
```

Pydantic Settings parses safe runtime flags directly (for example,
`--stateless`, `--server-host`, and `--sync-safety-margin-minutes`). Credentials and
connection URLs are environment/dotenv-only; all settings use documented
`LUNCHMONEY_` environment variables.

The scheduler reports its most recent outcome at `GET /sync/status` and through
the `get_sync_status` MCP tool. It never runs in the Gunicorn web process. To
include the dedicated scheduler with the Compose deployment, use:

```bash
docker compose --profile scheduler up --build
```

Run exactly one scheduler process. APScheduler 3.11 is a stable runtime, but its
job stores cannot be shared across scheduler processes, so HA scheduling is not
supported. The web service can still run in multiple Gunicorn workers; scheduled
sync remains isolated in its dedicated process and uses the shared sync lock.

For local single-process FastAPI development, enable the optional scheduler in
the `serve` command:

```bash
task dev -- --embed-scheduler --schedule-cron "0 * * * *"
```

Embedded scheduling is disabled by default and only works with
`LUNCHMONEY_ENVIRONMENT=development` and one direct Uvicorn/FastAPI worker. Startup rejects
Gunicorn and configured multi-worker processes; use the dedicated scheduler
process in those deployments.

### REST API authentication

The REST API is open by default for local development. Set
`LUNCHMONEY_MCP_API_KEY` to require callers to provide the same value in the
`X-API-Key` request header:

```bash
export LUNCHMONEY_MCP_API_KEY="your-server-key"
task dev
```

`LUNCHMONEY_MCP_API_KEY` authenticates clients of this project; it is distinct
from `LUNCHMONEY_ACCESS_TOKEN`, the server's upstream Lunch Money credential.

### Remote MCP OAuth

For MCP clients that require OAuth, configure an OIDC identity provider and
start an HTTP transport:

```bash
export LUNCHMONEY_MCP_OAUTH_CONFIG_URL="https://id.example.com/.well-known/openid-configuration"
export LUNCHMONEY_MCP_OAUTH_CLIENT_ID="lunchmoney-mcp"
export LUNCHMONEY_MCP_OAUTH_CLIENT_SECRET="your-identity-provider-secret"
export LUNCHMONEY_MCP_OAUTH_BASE_URL="https://mcp.example.com"

task run -- lunchmoney-mcp mcp --streamable-http --host 0.0.0.0 --port 8000
```

The public base URL must match the deployed HTTPS origin. Register
`https://mcp.example.com/auth/callback` with the identity provider. OAuth is
disabled when these settings are unset, so local stdio clients still require no
client authentication.

## Database configuration

With no configuration, `LunchMoneyDatabase` uses the persistent SQLite file
`sqlite+aiosqlite:///lunchmoney.db` in the current working directory. Pass a URL to the
constructor or set `LUNCHMONEY_DATABASE_URL`; an explicit constructor URL takes
precedence. For example:

```text
sqlite+aiosqlite:////absolute/path/to/lunchmoney.db
postgresql+asyncpg://user:password@host/database
```

Create or update the schema before using the database. Runtime database construction
does not call `create_all()` or run migrations automatically.

```bash
export LUNCHMONEY_DATABASE_URL=sqlite+aiosqlite:///lunchmoney.db
uv run alembic upgrade head
```

The same command works with a `postgresql+asyncpg` URL. Run the following to reverse all
migrations:

```bash
uv run alembic downgrade base
```

## Public API and convenience CRUD

All database interfaces and records are available from one package:

```python
from lunchmoney_mcp.database import (
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

After applying the migration, use the convenience API for detached records and their
supported relationship graphs:

```python
from lunchmoney_mcp.database import LunchMoneyDatabase, User

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

`upsert_many()` persists several supported records atomically and orders dependencies
for you. The convenience CRUD methods support `User`, `PlaidAccount`, `ManualAccount`,
`Category`, `Tag`, and `Transaction`; owned attachment, tag-link, category-child, and
transaction-child records are persisted through their parent graphs.

## Native SQLModel sessions

Use `session()` when a query or transaction needs SQLModel directly. It yields a native
asynchronous `AsyncSession`; callers control commits for their own writes.

```python
from sqlmodel import select

from lunchmoney_mcp.database import LunchMoneyDatabase, User

async with LunchMoneyDatabase() as database:
    async with database.session() as session:
        result = await session.exec(select(User).where(User.account_id == 100))
        users = result.all()
```

## Generated-model conversion and account scope

Each primary record supplies `from_api()` to convert its generated
`lunchmoney.models` object and `to_api()` to reconstruct that object. Category and
transaction conversions preserve their complete child graphs; pass the available tags
to `Transaction.from_api()` when resolving transaction tag relationships.

```python
record = User.from_api(api_user)
restored_api_user = record.to_api()
```

A database is intentionally scoped to one Lunch Money budgeting account. Most tables do
not carry a tenant/account partition key, so do not mix data from multiple Lunch Money
accounts in one database. Use a separate SQLite file or PostgreSQL database/schema and a
separate `LunchMoneyDatabase` for each account.
