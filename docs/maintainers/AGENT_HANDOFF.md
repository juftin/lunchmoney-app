# 🤖 Lunch Money MCP — Master Agent Hand-off Technical Specification

## 📋 Executive Overview & Purpose

This document is an **exhaustive hand-off guide** for AI coding agents and human engineers maintaining **Lunch Money MCP**. It records architectural conventions, the completed implementation history through Sprint 7, and the prioritized operational-product roadmap that follows completion of the Lunch Money v2 API coverage matrix.

The active persistence-mode migration supersedes this document wherever it
describes persistence-mode behavior. Implementation agents must
read [`DESIGN_EPHEMERAL_STATEFUL.md`](DESIGN_EPHEMERAL_STATEFUL.md),
[`EPHEMERAL_ENDPOINT_MATRIX.md`](EPHEMERAL_ENDPOINT_MATRIX.md),
[`EPHEMERAL_IMPLEMENTATION_HANDOFF.md`](EPHEMERAL_IMPLEMENTATION_HANDOFF.md),
and [`EPHEMERAL_VERIFICATION.md`](EPHEMERAL_VERIFICATION.md). Completed sprint
descriptions below remain historical records of the current implementation.

---

## 🏛️ System Architectural Principles & Conventions

### 1. Codebase Architecture & Layering Rules

- **Services Layer (`src/lunchmoney_app/services/`)**: All business logic, DB queries, API calls, and domain rollups **must** reside in `services/`.
- **FastAPI Routers (`src/lunchmoney_app/app/routers/`)**: Routers must be clean 1-to-2 line delegators calling service functions.
- **FastMCP Server (`src/lunchmoney_app/mcp/server.py`)**: FastMCP tools must be clean 1-to-2 line delegators calling the exact same service functions as FastAPI routers. FastMCP tools are explicitly registered via `@mcp.tool()`, so route `operation_id` alignment is decoupled and not required.
- **Upstream-First Mutation Pattern**: All write operations (create/update/delete) **must** call the Lunch Money v2 API first. The canonical response is authoritative. The selected stateful projector reconciles SQLModel storage; ephemeral mode retains no projection.

### 2. Code Quality & Verification Standard

Before committing any code, any agent **must** execute:

```bash
task fix && task lint && task check && task test
```

All four commands must exit with status `0` and 0 errors.

### 3. Git Commit Conventions

All commits **must** use the Gitmoji convention:

```
<intention> [scope?][:?] <message>
```

---

## 🗺️ Master Sprint Implementation Roadmap

```mermaid
graph LR
    S0[Sprint 0: Incremental ETL] --> S1[Sprint 1: Complete Read-Only Coverage]
    S1 --> S2[Sprint 2: Category & Account Mutations]
    S2 --> S3[Sprint 3: Transaction Mutations & Splits]
    S3 --> S4[Sprint 4: Budgets & Spending Trends]
    S4 --> S5[Sprint 5: Production Security & CI/CD]
    S5 --> S6[Sprint 6: Remote MCP OAuth]
    S6 --> S7[Sprint 7: Tag Mutations & v2 Completion]
    S7 --> S8[Sprint 8: Runtime & Scheduled Sync]
    S8 --> S9[Sprint 9: Upstream Compatibility]
    S9 --> S10[Sprint 10: Hardening & Observability]
    S10 --> S11[Sprint 11: Server-Rendered Dashboard]
    S11 --> S12[Sprint 12: CLI & Operator Experience]
```

---

## 🛠️ Sprint Specifications

### Sprint 0: Incremental ETL

Completed: `SyncMetadata` watermark tracking, opt-in incremental sync (`incremental=True`), configurable safety overlap margins (`LUNCHMONEY_SYNC_SAFETY_MARGIN_MINUTES`), and the stateful-only synchronization boundary.

### Sprint 1: Complete Read-Only 100% v2 API Coverage

Completed: `/summary`, `/tags`, `/recurring_items`, `/categories/{id}`, `/manual_accounts/{id}`, `/plaid_accounts/{id}`, and `/transactions/{id}` read operations.

### Sprint 2: Category & Manual Account Mutations

Completed: `POST`, `PUT`, and `DELETE` for categories and manual accounts using the upstream-first write-back pattern.

### Sprint 3: Transaction Mutations, Grouping, Splitting & Attachments

Completed: single and bulk transaction CRUD, transaction grouping, transaction splitting, and file attachment operations.

### Sprint 4: Budgets & Spending Trends

Completed: `GET /api/budgets/settings`, `PUT /api/budgets`, `DELETE /api/budgets`, and `GET /api/spending/trends`.

### Sprint 5: Production Security & CI/CD

Completed: REST API-key authorization, the MCP executable with mutually exclusive stdio/SSE/HTTP/Streamable HTTP transports, MCP resources and prompts, and GitHub Actions validation.

### Sprint 6: Remote MCP OAuth & Roadmap Reconciliation

Completed: optional OIDC OAuth protection for remote MCP HTTP transports, OAuth deployment guidance, and roadmap reconciliation.

### Sprint 7: Tag Mutations & API Coverage Completion

Completed: upstream-first tag `POST`, `PUT`, and `DELETE` operations through REST and MCP, including cached transaction-tag link cleanup. The documented Lunch Money v2 API matrix is now complete.

### Sprint 8: Production Runtime & Scheduled Sync

Completed: The executable has dedicated `mcp`, `serve`, `schedule`, and `sync` runtimes. MCP stdio defaults to database-free ephemeral operation; HTTP defaults to stateful synchronized storage. The shared `--persistence-mode` option accepts exactly `stateful` or `ephemeral`. Dashboard, synchronization, cache status, watermarks, and scheduling are stateful-only. Gunicorn with the maintained Uvicorn worker package serves production HTTP. The opt-in APScheduler 3.11-driven `lunchmoney-app schedule` process runs cron-based sync with timezone configuration, missed-run coalescing, one-at-a-time execution, persisted run reporting, and a shared migration/sync lock. Scheduler work is isolated from Gunicorn workers. `LUNCHMONEY_EMBED_SCHEDULER=true` is supported only for a local, direct single-worker FastAPI process; it is rejected under Gunicorn, multi-worker, non-development, and ephemeral configurations.

### Sprint 9: Upstream API Compatibility & Coverage Audit

Completed: pin the generated client and upstream OpenAPI package, snapshot their
paths, operations, schemas, and enum values, and enforce that review in CI.
`docs/upstream-coverage.json` maps all 39 generated operations through service,
REST, and MCP layers. CI also runs read-only checks against Lunch Money's
official static mock with a synthetic token. See
[`UPSTREAM_COMPATIBILITY.md`](UPSTREAM_COMPATIBILITY.md) for the upgrade and
breaking-change policy.

### Sprint 10: Operational Hardening & Observability

Completed: `/health` exposes liveness and `/ready` reports database and embedded-scheduler readiness without sensitive details. JSON request logs, request IDs, safe error responses, and API-key-protected Prometheus metrics cover HTTP/MCP traffic, upstream failures, sync duration, and cache freshness. The top-level REST/MCP application applies explicit proxy, host, CORS, body-size, timeout, concurrency, and rate-limit policies with safe defaults. Production Compose runs hardened non-root containers with private data services; CI scans filesystem and image artifacts and performs a Compose liveness/readiness smoke test. See [`OPERATIONS.md`](../OPERATIONS.md) for TLS, secret rotation, backup/restore, retention, and incident response.

### Sprint 11: Server-Rendered Financial Dashboard

Planned: a single-user, single–Lunch Money-account, authenticated and accessible FastAPI HTML dashboard using server-rendered templates and existing services. It must not become a separate JavaScript application or duplicate service-layer analytics.

### Sprint 12: CLI, Packaging & Operator Experience

Planned: evolve the executable into `mcp`, `serve`, `schedule`, `sync`, `doctor`, and `version` subcommands, with clear transport help, redacted diagnostics, documented config precedence, and Docker Compose-first deployment/upgrade examples.
