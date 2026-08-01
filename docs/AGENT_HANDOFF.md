# 🤖 Lunch Money MCP — Master Agent Hand-off Technical Specification

## 📋 Executive Overview & Purpose

This document is an **exhaustive hand-off guide** for AI coding agents and human engineers maintaining **Lunch Money MCP**. It records architectural conventions, the completed implementation history through Sprint 7, and the prioritized operational-product roadmap that follows completion of the Lunch Money v2 API coverage matrix.

---

## 🏛️ System Architectural Principles & Conventions

### 1. Codebase Architecture & Layering Rules

- **Services Layer (`src/lunchmoney_mcp/services/`)**: All business logic, DB queries, API calls, and domain rollups **must** reside in `services/`.
- **FastAPI Routers (`src/lunchmoney_mcp/app/routers/`)**: Routers must be clean 1-to-2 line delegators calling service functions.
- **FastMCP Server (`src/lunchmoney_mcp/mcp/server.py`)**: FastMCP tools must be clean 1-to-2 line delegators calling the exact same service functions as FastAPI routers. FastMCP tools are explicitly registered via `@mcp.tool()`, so route `operation_id` alignment is decoupled and not required.
- **Upstream-First Mutation Pattern**: All write operations (create/update/delete) **must** call the Lunch Money v2 API first. Upon receiving the canonical API response object, the service converts it to a SQLModel record (`Model.from_api()`) and executes `await db.upsert()` or `await db.delete()`.

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
    S0[Sprint 0: Incremental ETL & Stateless Engine] --> S1[Sprint 1: Complete Read-Only Coverage]
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

### Sprint 0: Incremental ETL & Stateless Engine

Completed: `SyncMetadata` watermark tracking, opt-in incremental sync (`incremental=True`), configurable safety overlap margins (`LUNCHMONEY_SYNC_SAFETY_MARGIN_MINUTES`), and in-memory SQLite support (`STATELESS=true`).

### Sprint 1: Complete Read-Only 100% v2 API Coverage

Completed: `/summary`, `/tags`, `/recurring_items`, `/categories/{id}`, `/manual_accounts/{id}`, `/plaid_accounts/{id}`, and `/transactions/{id}` read operations.

### Sprint 2: Category & Manual Account Mutations

Completed: `POST`, `PUT`, and `DELETE` for categories and manual accounts using the upstream-first write-back pattern.

### Sprint 3: Transaction Mutations, Grouping, Splitting & Attachments

Completed: single and bulk transaction CRUD, transaction grouping, transaction splitting, and file attachment operations.

### Sprint 4: Budgets & Spending Trends

Completed: `GET /budgets/settings`, `PUT /budgets`, `DELETE /budgets`, and `GET /spending/trends`.

### Sprint 5: Production Security & CI/CD

Completed: REST API-key authorization, the MCP executable with mutually exclusive stdio/SSE/HTTP/Streamable HTTP transports, MCP resources and prompts, and GitHub Actions validation.

### Sprint 6: Remote MCP OAuth & Roadmap Reconciliation

Completed: optional OIDC OAuth protection for remote MCP HTTP transports, OAuth deployment guidance, and roadmap reconciliation.

### Sprint 7: Tag Mutations & API Coverage Completion

Completed: upstream-first tag `POST`, `PUT`, and `DELETE` operations through REST and MCP, including cached transaction-tag link cleanup. The documented Lunch Money v2 API matrix is now complete.

### Sprint 8: Production Runtime & Scheduled Sync

Completed: The executable has three runtime commands: `mcp` serves only the MCP transports with an ephemeral in-memory schema and no scheduler; `serve` runs the persistent FastAPI application and its MCP routes in one local Uvicorn process, optionally with the embedded scheduler; and `schedule` runs only scheduled sync. Gunicorn with the maintained Uvicorn worker package serves production HTTP. The opt-in APScheduler 3.11-driven `lunchmoney-mcp schedule` process runs cron-based sync with timezone configuration, missed-run coalescing, one-at-a-time execution, persisted run reporting, and a shared migration/sync lock. The `serve` and `schedule` commands use Pydantic Settings' native kebab-case CLI flags, with their resolved settings shared by the FastAPI lifespan and scheduled jobs. Scheduler work is isolated from Gunicorn workers. `LUNCHMONEY_EMBED_SCHEDULER=true` is supported only for a local, direct single-worker FastAPI process; it is rejected under Gunicorn, multi-worker, and non-development configurations. APScheduler 3 job stores cannot be shared, so production uses one scheduler process plus any number of web workers.

### Sprint 9: Upstream API Compatibility & Coverage Audit

Completed: pin the generated client and upstream OpenAPI package, snapshot their
paths, operations, schemas, and enum values, and enforce that review in CI.
`docs/upstream-coverage.json` maps all 39 generated operations through service,
REST, and MCP layers. CI also runs read-only checks against Lunch Money's
official static mock with a synthetic token. See
[`UPSTREAM_COMPATIBILITY.md`](UPSTREAM_COMPATIBILITY.md) for the upgrade and
breaking-change policy.

### Sprint 10: Operational Hardening & Observability

Completed: `/health` exposes liveness and `/ready` reports database and embedded-scheduler readiness without sensitive details. JSON request logs, request IDs, safe error responses, and API-key-protected Prometheus metrics cover HTTP/MCP traffic, upstream failures, sync duration, and cache freshness. The top-level REST/MCP application applies explicit proxy, host, CORS, body-size, timeout, concurrency, and rate-limit policies with safe defaults. Production Compose runs hardened non-root containers with private data services; CI scans filesystem and image artifacts and performs a Compose liveness/readiness smoke test. See [`OPERATIONS.md`](OPERATIONS.md) for TLS, secret rotation, backup/restore, retention, and incident response.

### Sprint 11: Server-Rendered Financial Dashboard

Planned: a single-user, single–Lunch Money-account, authenticated and accessible FastAPI HTML dashboard using server-rendered templates and existing services. It must not become a separate JavaScript application or duplicate service-layer analytics.

### Sprint 12: CLI, Packaging & Operator Experience

Planned: evolve the executable into `mcp`, `serve`, `schedule`, `sync`, `doctor`, and `version` subcommands, with clear transport help, redacted diagnostics, documented config precedence, and Docker Compose-first deployment/upgrade examples.
