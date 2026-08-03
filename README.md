<h1 align="center">lunchmoney-mcp</h1>

<p align="center">
    Lunch Money Application
</p>

<p align="center">
  <a href="https://github.com/juftin/lunchmoney-mcp"><img src="https://img.shields.io/github/v/release/juftin/lunchmoney-mcp?color=blue&label=lunchmoney-mcp&logo=github" alt="GitHub"></a>
  <a href="https://github.com/juftin/lunchmoney-mcp/blob/main/LICENSE"><img src="https://img.shields.io/github/license/juftin/lunchmoney-mcp?color=blue&label=License" alt="GitHub License"></a>
  <a href="https://github.com/juftin/lunchmoney-mcp/actions/workflows/ci.yaml?query=branch%3Amain"><img src="https://github.com/juftin/lunchmoney-mcp/actions/workflows/ci.yaml/badge.svg?branch=main" alt="CI Status"></a>
  <a href="https://github.com/go-task/task"><img src="https://img.shields.io/badge/task---?message=task&logo=task&color=teal&labelColor=grey" alt="task"></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv"></a>
  <a href="https://github.com/pre-commit/pre-commit"><img src="https://img.shields.io/badge/pre--commit-enabled-lightgreen?logo=pre-commit" alt="pre-commit"></a>
  <a href="https://juftin.github.io/lunchmoney-mcp/"><img src="https://img.shields.io/static/v1?message=docs&color=526CFE&logo=Material+for+MkDocs&logoColor=FFFFFF&label=" alt="docs"></a>
  <a href="https://github.com/semantic-release/semantic-release"><img src="https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079.svg" alt="semantic-release"></a>
  <a href="https://gitmoji.dev"><img src="https://img.shields.io/badge/gitmoji-%20😜%20😍-FFDD67.svg" alt="Gitmoji"></a>
</p>

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

Docker Compose is the supported production deployment path. By default it runs
the combined REST and streamable-HTTP MCP application with Gunicorn and
`uvicorn-worker` on port 8000. The Compose stack binds HTTP only to loopback
and requires explicit production credentials. See the
[operations runbook](docs/OPERATIONS.md) for API-only, MCP-only, combined, and
dedicated-scheduler topologies, plus TLS, secrets, backup, restore, retention,
and upgrade procedures.

```bash
export LUNCHMONEY_ACCESS_TOKEN="your-lunch-money-token"
export LUNCHMONEY_MCP_API_KEY="your-server-key"
export POSTGRES_USER="lunchmoney"
export POSTGRES_PASSWORD="use-a-long-random-password"
export POSTGRES_DB="lunchmoney"
export LUNCHMONEY_DATABASE_URL="postgresql+asyncpg://lunchmoney:use-a-long-random-password@postgres:5432/lunchmoney"
task compose
```

## Configuration and CLI

The command-line interface provides `mcp`, `serve`, `schedule`, `sync`,
`doctor`, and `version`. Use command help to see the options applicable to one
runtime:

```bash
lunchmoney-mcp --help
lunchmoney-mcp mcp --help
```

For safe, CLI-exposed runtime settings, precedence is **CLI flags > process
environment > `.env` > built-in defaults**. For example, a `--port` flag wins
over `LUNCHMONEY_PORT`, which wins over `LUNCHMONEY_PORT` in `.env`. Secrets
and connection URLs are deliberately environment/`.env`-only and cannot be
passed as command-line flags.

Use a `.env` file for local development and a secret manager or the deployment
environment in production. Docker Compose also reads its project `.env` file
to interpolate the Compose file; values passed into the container are process
environment values and therefore take precedence over an application `.env`
file inside the image.

`doctor` is local-only: it validates configuration and local prerequisites
without making a Lunch Money API request. Its output redacts secret values.
`sync` performs one foreground synchronization; `version` prints the installed
package version.

### Shell completion

The CLI uses standard `--help` output and does not install shell completion
automatically. Enable completion for the shell wrapper you use (for example,
`uvx` or your package manager) and delegate arguments to `lunchmoney-mcp`; the
subcommand is the first argument. Completion is convenience only—use
`lunchmoney-mcp <subcommand> --help` as the authoritative option list.

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

Pydantic Settings parses safe runtime flags only for the command that uses them:
`mcp` exposes transport, OAuth, `--host`, and `--port`; `schedule` exposes
scheduling and `--stateless`; `sync` exposes its foreground sync options and
`--stateless`; and `serve` exposes its web-server, scheduler, sync, and OAuth
options. `doctor` and `version` accept no runtime configuration flags.
Credentials and connection URLs are environment/`.env`-only; all settings use
documented `LUNCHMONEY_` environment variables.

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
