# Ephemeral and Stateful Verification Playbook

## Purpose

This playbook defines the evidence required to accept the persistence-mode
implementation. It is written as behavioral guidance for test authors and
reviewers; it does not prescribe test implementation code.

The design is not complete merely because existing tests pass. New tests must
prove the absence of database behavior and cross-operation retention in
ephemeral mode, plus continued stateful behavior.

## Verification Layers

| Layer                 | Proves                                                                         | Typical location                                                |
| --------------------- | ------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| Configuration         | Valid modes, defaults, explicit-source conflicts, scheduler conflicts          | `tests/test_config.py`, CLI/doctor tests                        |
| Context lifecycle     | One context per operation, cleanup, memo isolation, no fallback                | `tests/test_operations.py`                                      |
| Reader contracts      | Canonical types and equivalent semantics for matched source data               | New focused reader-contract tests or existing domain test files |
| Mutation contracts    | Upstream authority, projection, invalidation, failure behavior                 | Existing mutation test files                                    |
| Transport parity      | REST/MCP/resources map the same services and errors                            | `tests/test_app.py`, `tests/test_mcp.py`, collection contracts  |
| Architecture guards   | Ephemeral cannot construct or resolve persistence                              | New focused persistence-mode guard tests                        |
| Stateful regression   | Migrations, sync, locks, cache, scheduler, and projection remain intact        | Existing database/sync/scheduler suites                         |
| End-to-end acceptance | Supported public surfaces work in both modes or return the documented boundary | Mode-parametrized application tests                             |

## Configuration Matrix

Test each row independently. “Explicit database” means supplied through a
supported configuration source rather than inherited from the model default.

| Runtime            | Mode input        | Database input            | Scheduler input               | Expected result                                                |
| ------------------ | ----------------- | ------------------------- | ----------------------------- | -------------------------------------------------------------- |
| HTTP serve         | Omitted           | Omitted                   | Disabled                      | Stateful using default database URL                            |
| HTTP serve         | `stateful`        | Omitted                   | Disabled                      | Stateful using default database URL                            |
| HTTP serve         | `stateful`        | Explicit file SQLite      | Disabled                      | Accepted                                                       |
| HTTP serve         | `stateful`        | Explicit PostgreSQL       | Disabled                      | Accepted                                                       |
| HTTP serve         | `stateful`        | Explicit memory SQLite    | Disabled                      | Accepted as stateful database configuration                    |
| HTTP serve         | `ephemeral`       | Omitted                   | Disabled                      | Accepted without resolving a database                          |
| HTTP serve         | `ephemeral`       | Any explicit database URL | Disabled                      | Configuration error before startup                             |
| HTTP serve         | `ephemeral`       | Omitted                   | Any enabled scheduler setting | Configuration error before startup                             |
| MCP stdio          | Omitted           | Omitted                   | Not exposed                   | Ephemeral default                                              |
| MCP stdio          | `stateful`        | Omitted or explicit       | Not exposed                   | Stateful                                                       |
| MCP stdio          | `ephemeral`       | Explicit database         | Not exposed                   | Configuration error                                            |
| MCP HTTP           | Omitted           | Omitted                   | Not exposed                   | Stateful default                                               |
| Dedicated schedule | `ephemeral`       | Any                       | Enabled by command purpose    | Configuration/usage error                                      |
| Foreground sync    | `ephemeral`       | Omitted                   | Disabled                      | Nonzero `stateful_mode_required` result without storage access |
| Any runtime        | Invalid mode text | Any                       | Any                           | Validation error naming valid choices                          |

Also verify that the default database URL does not appear as explicitly supplied
and accidentally prevent the stdio ephemeral default.

## Architectural Guard Specifications

Run representative ephemeral REST requests, MCP tool calls, and MCP resource
reads with persistence entrypoints replaced by sentinels that fail immediately.
The operation must still succeed when it is classified **Both**, or return its
documented mode error when stateful-only.

Sentinel targets include:

- `LunchMoneyDatabase` construction;
- SQLAlchemy async engine construction;
- database URL resolution;
- `get_shared_database`;
- migrations and schema creation;
- migration and synchronization lock factories;
- SQLModel conversion methods such as `from_api()`;
- database sessions, cached-response helpers, and `SyncMetadata` access.

These tests must exercise real transport/context wiring. A unit test that calls
an ephemeral reader directly does not prove the application avoided database
fallback elsewhere.

### Negative source scan

At final review, search supported runtime code for:

- `settings.stateless` or boolean mode selection;
- `settings.ephemeral` after conversion to the enum contract;
- `IN_MEMORY_DATABASE_URL`;
- `is_stateless`;
- `live=` service switches;
- `Database | None` used to represent runtime mode;
- `get_settings()` inside domain services;
- `get_operation_database() or get_shared_database()`-style fallback;
- private `mode=memory` URLs created for an operation.

Matches in explicitly stateful backend compatibility handling are acceptable
only when they do not select a persistence mode.

## Operation Context and Memo Cases

Verify all of the following:

- REST request, MCP tool call, and MCP resource read each bind one context.
- An exception in a service still resets and disposes the context.
- The next operation cannot read the prior operation's memo.
- Equivalent concurrent reads inside one operation produce one upstream call.
- Queries differing by any parameter do not collide.
- Failed upstream reads are not memoized.
- Mutating a returned collection cannot alter a later memoized result.
- A successful create/update/delete invalidates every related memo key listed in
  the endpoint matrix.
- A mutation failure leaves successfully memoized pre-mutation reads intact.
- A context accessor used outside its lifetime raises rather than resolving a
  database or creating a new context.
- Background tasks cannot continue using the exited context.
- The cached `LunchMoneyApp` instance has no retained financial models after an
  ephemeral operation.

## Canonical Fixture Catalog

Use only synthetic values. Reuse the same logical source dataset for stateful
and ephemeral adapter tests.

### Categories

Include:

- one ordinary expense category;
- one income category;
- one category group with two children;
- one archived or excluded category;
- explicit order values and one missing order;
- transactions assigned directly to a group, to children, and to no category.

Expected cases cover nested and flattened output, `is_group` filtering,
category-group transaction filters, sort order, and parent/child detail shape.

### Accounts

Include manual, Plaid, and cash transactions; an archived or closed account;
multiple currencies; and account deletion with both relationship-preserving and
item-deleting options. Verify account ID `0` cash-filter semantics for
transactions.

### Tags

Include two tags with full style metadata, a transaction using both tags, a tag
filter, tag update, and forced deletion. Verify transaction metadata and links
remain equivalent after normalization.

### Transactions

Include:

- records on inclusive start/end boundaries;
- created/updated timestamps around UTC cutoffs;
- cleared and pending records;
- uncategorized and cash records;
- manual and Plaid accounts;
- category-group children;
- tagged and untagged records;
- a group parent with children;
- a split parent with children;
- attachments and file flags;
- enough records to require multiple upstream pages;
- equal dates with different IDs to verify secondary ordering.

Exercise every `TransactionQuery` control individually and in representative
combinations. Do not rely only on response-schema assertions.

### Summary and recurring

Include excluded budget categories, in-range and past occurrences, totals,
rollover data, active recurring items, and suggested recurring items. Verify
every optional response control and date-window key.

### Analytics

Include expense, income, uncategorized, group-child, split-parent, and ordinary
transactions across day, week, month, and year boundaries. Verify inclusive
periods, Monday week starts, chronological trend order, counts, and exact
category rollups.

## Reader Contract Matrix

For equivalent source fixtures, run both stateful and ephemeral readers against
the same behavioral assertions:

| Contract                  | Collection readers               | Detail readers                                                                      | Analytics sources                     |
| ------------------------- | -------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------- |
| Canonical API models only | Required                         | Required                                                                            | Required source values                |
| Complete pagination       | Required when upstream paginates | Not applicable                                                                      | Required through transaction source   |
| Filtering parity          | Required                         | Parameter parity                                                                    | Inclusive date bounds                 |
| Deterministic ordering    | Required                         | Not applicable                                                                      | Chronological/report ordering         |
| Not-found/error mapping   | Upstream failures preserved      | Upstream 404 becomes `None` for nullable detail contracts; other failures propagate | Upstream source errors fail operation |
| No source retention       | Ephemeral only                   | Ephemeral only                                                                      | Ephemeral only                        |
| No stale fallback         | Ephemeral only                   | Ephemeral only                                                                      | Ephemeral only                        |

Schema equality alone is insufficient. Compare normalized model values and
ordering.

## Mutation Contract Matrix

Every mutation family must cover these scenarios:

| Scenario                             | Expected upstream calls | Stateful projection               | Ephemeral projection   | Response                                 |
| ------------------------------------ | ----------------------- | --------------------------------- | ---------------------- | ---------------------------------------- |
| Upstream failure                     | One attempted call      | None                              | None                   | Mapped upstream failure                  |
| Upstream success                     | One call                | Required domain projection        | None                   | Canonical success                        |
| Upstream success, projection failure | One call                | Mark stale/degrade health         | Not applicable         | Canonical success, not a generic failure |
| Read then mutate then read           | One mutation            | Projection plus memo invalidation | Memo invalidation only | Post-mutation live/canonical value       |
| Caller repeats mutation explicitly   | One call per invocation | Normal projection                 | None                   | No hidden automatic retry                |

Deletion tests must prove ephemeral mode performs no database relationship scan.
Attachment upload tests must prove file bytes are not retained in the memo or
shared client. Ungroup tests must prove child IDs are acquired before the
destructive upstream call.

## Mode-Error Transport Contract

Use a single service-domain error and verify mappings independently.

### REST

- Status: `409 Conflict`.
- JSON body:

    ```json
    {
        "detail": {
            "code": "stateful_mode_required",
            "message": "This operation requires stateful persistence mode."
        }
    }
    ```

- Dashboard and HTMX requests receive the same JSON contract.
- The error occurs before database dependency resolution, locking, or upstream
  access.

### MCP

- Tool result has `isError: true`.
- Text content serializes the same code and safe message.
- Resource failures use the equivalent MCP error path.
- No Python traceback, database URL, or configuration secret reaches content.

### CLI

- Safe message contains the stable code or its exact documented explanation.
- Exit status is nonzero.
- No database, migration, or lock is initialized first.

## Health and Observability

Ephemeral-mode tests must prove:

- liveness succeeds without database or upstream probes;
- readiness reflects valid local configuration without treating Lunch Money
  availability as a readiness dependency;
- explicitly invalid database/scheduler combinations fail before serving;
- metrics and logs identify persistence mode without including financial
  payloads, tokens, database credentials, query values containing user data, or
  attachment bytes;
- upstream failures increment safe failure telemetry but do not trigger stale
  fallback;
- stateful projection failure degrades cache health and readiness as designed.

Stateful tests must continue proving database readiness, migration locking,
scheduler readiness, cache freshness, and disposal.

## Stateful Regression Inventory

Do not weaken or delete coverage for:

- SQLite and PostgreSQL URL resolution;
- explicitly configured memory SQLite pooling compatibility;
- migrations and schema contract;
- CRUD persistence and relationship reconciliation;
- full and incremental synchronization;
- watermark safety margins;
- migration and sync locks;
- cached summary, budget, and recurring snapshots;
- scheduled run persistence and status;
- embedded and dedicated scheduler constraints;
- dashboard rendering, partial section tolerance, and dashboard-triggered sync
  in stateful mode;
- upstream compatibility manifest and mock-service coverage.

When an old test names `stateless`, replace it with a new contract assertion or
delete it only when its behavior is intentionally removed. Do not mechanically
rename old shared-memory behavior to ephemeral.

## Packet Gates

Each implementation packet runs focused tests for its files plus:

```text
task check:style
task check:types
```

Packet owners must report exact commands and failures. The final integration
owner runs:

```text
task fix
task lint
task check
task test
```

If generated-client call paths or coverage mappings change, also run:

```text
task upstream:check
task contract
```

## Final Review Checklist

- [ ] Only `stateful` and `ephemeral` are supported runtime modes.
- [ ] Explicit database configuration conflicts with ephemeral mode.
- [ ] Enabled scheduling conflicts with ephemeral mode.
- [ ] Stateful memory URLs remain ordinary explicit backend configuration.
- [ ] Ephemeral transport operations construct no database or SQL engine.
- [ ] Ephemeral startup runs no migration, schema creation, or lock.
- [ ] Ephemeral operations retain no financial models across context exit.
- [ ] Services do not select modes through settings or `live` booleans.
- [ ] SQLModel records remain behind stateful adapters.
- [ ] All **Both** rows in the endpoint matrix have live-path tests.
- [ ] Every stateful-only row returns the shared domain error before data access.
- [ ] REST and MCP share semantics and error codes.
- [ ] Pagination and query parity use behavioral fixtures.
- [ ] Analytics use bounded periods and shared aggregation logic.
- [ ] Mutations are not automatically retried.
- [ ] Projection failure preserves upstream success and marks cache health stale.
- [ ] Mutation invalidation prevents operation-local stale reads.
- [ ] Dashboard is unavailable in ephemeral and unchanged in stateful mode.
- [ ] Health/readiness behavior matches both mode contracts.
- [ ] Existing stateful migrations, sync, locks, scheduler, and dashboard pass.
- [ ] Supported user/operator documentation describes only the new modes.
- [ ] Full required task commands exit zero.

An unchecked item blocks completion unless the design is explicitly revised.
