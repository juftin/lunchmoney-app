# Sprint 0: Incremental ETL and Stateless Engine Design

## Goal

Provide an opt-in incremental synchronization mode backed by durable per-domain
watermarks, while allowing fully ephemeral operation with `STATELESS=true`.

## Scope

Sprint 0 includes configuration, the `SyncMetadata` persistence model and
migration, shared in-memory SQLite initialization, incremental transaction
filtering, REST/MCP parameters, and regression tests. It does not change the
default 30-day synchronization behavior or add any new Lunch Money endpoints.

## Configuration

`Settings` will expose:

- `stateless: bool`, sourced from `STATELESS` and defaulting to `False`.
- `sync_safety_margin_minutes: int`, sourced from
  `LUNCHMONEY_SYNC_SAFETY_MARGIN_MINUTES` and defaulting to `5`.

When `stateless` is enabled and no explicit database URL is supplied, the
database resolves to a shared in-memory SQLite URI. An explicit
`LUNCHMONEY_DATABASE_URL` continues to take precedence so deployments can
override the mode deliberately.

## Persistence

`SyncMetadata` contains one record per synchronized domain. Its primary key is
the domain name and its `last_synced_at` value is a timezone-aware UTC
timestamp. The database wrapper provides `create_tables()` for stateless
operation, creating all SQLModel tables on the `StaticPool`-backed shared
connection. Persistent deployments continue to use Alembic migrations.

## Synchronization flow

`incremental=False` remains the default and uses the current rolling `days`
transaction window. With `incremental=True`, synchronization reads the
transactions watermark. If present, it subtracts either the request's
`safety_margin_minutes` or the configured default, converts the result to the
upstream `updated_since` argument, and requests the overlapping transaction
changes. If no watermark exists, it falls back to the rolling window.

Only after a successful database upsert does synchronization write the new UTC
watermark. A failed upstream refresh or persistence operation therefore leaves
the existing watermark unchanged. The initial implementation tracks the
`transactions` domain because it is the only currently supported upstream
request with `updated_since` filtering.

## Interfaces

`POST /api/sync` and the `sync_data` MCP tool will accept `incremental: bool =
False` and `safety_margin_minutes: int | None = None`. The service layer owns
the policy and forwards the resolved arguments to the application sync
function; routers and MCP tools remain delegators.

## Testing

Focused tests will verify settings parsing, stateless database persistence,
metadata migration/schema creation, fallback behavior with no watermark,
overlap calculation with a watermark, successful watermark advancement, and
the guarantee that a failing sync does not advance it. Existing default-sync
tests remain the regression coverage for backward compatibility.

## Non-goals

- Incremental filtering for resources other than transactions.
- Changing the default persistent SQLite mode.
- Changing client API semantics beyond passing `updated_since` to the existing
  transaction refresh method.
