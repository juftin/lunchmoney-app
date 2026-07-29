# 📋 Master Development Checklist & Agent Execution Guide

This document serves as the **operational task tracker** for **`lunchmoney-mcp`**. Every task across all implementation sprints is tracked here. AI agents and developers working on this project MUST follow the execution rules below.

---

## 🤖 Agent Operating Rules & Parallelization

### 1. How to Claim and Update Checklist Items

- Before starting a task, read the referenced specification in [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md) or [`docs/ROADMAP.md`](ROADMAP.md).
- When a task is fully verified (`task fix && task lint && task check && task test`), update this document by changing `- [ ]` to `- [x]`.
- If your work discovers new requirements, edge cases, or sub-tasks, immediately add new checklist items under the appropriate sprint section.

### 2. Subagent Creation & Parallelization Protocol

When a sprint contains independent, non-overlapping tasks (e.g. creating parallel service functions, adding independent endpoints, or writing unit tests), invoke subagents to execute them concurrently:

1. **Define Subagents (`define_subagent`)**:
   - Define specialized subagent roles (e.g., `EndpointBuilder`, `TestWriter`, `ServiceImplementor`).
2. **Invoke Subagents (`invoke_subagent`)**:
   - Launch subagents with clear, self-contained prompts specifying the target files and verification expectations.
3. **Reactive Notification (No Polling)**:
   - After launching subagents, do NOT poll in a loop. Stop tool calls or proceed with independent work until the system automatically notifies you upon completion.

---

## 🎯 Master Implementation Checklist

### 🏁 Sprint 0: Incremental ETL & Stateless Engine

_Reference Spec_: [`docs/INCREMENTAL_ETL.md`](INCREMENTAL_ETL.md) & [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md#sprint-0-incremental-etl--stateless-engine)

- [x] **MCP Tools Modularization**: Refactor FastMCP tools into modular domain package in [`src/lunchmoney_mcp/mcp/tools/`](../src/lunchmoney_mcp/mcp/tools/).
- [x] **Config Additions**: Add `stateless: bool` (`STATELESS`) and `sync_safety_margin_minutes: int` (`LUNCHMONEY_SYNC_SAFETY_MARGIN_MINUTES`) in [`src/lunchmoney_mcp/config.py`](../src/lunchmoney_mcp/config.py).
- [x] **SyncMetadata Model**: Create `SyncMetadata` table in [`src/lunchmoney_mcp/database/models/sync.py`](../src/lunchmoney_mcp/database/models/sync.py).
- [x] **Alembic Migration**: Add migration `0002_add_sync_metadata_table.py` for `sync_metadata`.
- [x] **Stateless In-Memory Database**: Update [`src/lunchmoney_mcp/database/backend.py`](../src/lunchmoney_mcp/database/backend.py) to support `StaticPool` in-memory SQLite and `create_tables()` helper.
- [x] **Opt-In Incremental Sync Logic**: Update [`src/lunchmoney_mcp/app/sync.py`](../src/lunchmoney_mcp/app/sync.py) & [`src/lunchmoney_mcp/services/sync.py`](../src/lunchmoney_mcp/services/sync.py) to handle transaction-only `incremental: bool = False` and `updated_since` timestamp filtering.
- [x] **Router & Tool Integration**: Expose `incremental` and `safety_margin_minutes` parameters on `POST /sync` and `sync_data` FastMCP tool.
- [x] **Test Suite**: Cover stateless configuration, database initialization, migrations, incremental transaction policy, and transport delegation in `tests/test_config.py`, `tests/database/test_backend.py`, `tests/database/test_migrations.py`, `tests/test_incremental_sync.py`, `tests/test_app.py`, and `tests/test_mcp.py`.

---

### 📖 Sprint 1: Read-Only 100% v2 API Coverage

_Reference Spec_: [`docs/ROADMAP.md`](ROADMAP.md#1-user--account-summary-me-summary) & [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md#sprint-1-complete-read-only-100-v2-api-coverage)

- [x] **Account Summary**: Implement `fetch_account_summary`, `GET /summary`, and `get_account_summary` FastMCP tool.
- [x] **Tags Queries**: Implement `fetch_tags`, `fetch_tag_by_id`, `GET /tags`, `GET /tags/{id}`, `list_tags`, and `get_tag` tools.
- [x] **Recurring Items Queries**: Implement `fetch_recurring_items`, `fetch_recurring_item_by_id`, `GET /recurring_items`, `GET /recurring_items/{id}`, `list_recurring_items`, and `get_recurring_item` tools.
- [x] **Single-ID Category Lookup**: Implement `GET /categories/{id}` and `get_category` FastMCP tool.
- [x] **Single-ID Account Lookups**: Implement `GET /accounts/manual/{id}` (`get_manual_account`) and `GET /accounts/plaid/{id}` (`get_plaid_account`).
- [x] **Single-ID Transaction Lookup**: Implement `GET /transactions/{id}` and `get_transaction` FastMCP tool.
- [x] **Test Suite**: Add tests for all read-only endpoints in `tests/test_read_only.py`.

---

### ✍️ Sprint 2: Category & Manual Account Mutations

_Reference Spec_: [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md#sprint-2-category--manual-account-mutations)

- [ ] **Category Creation**: Implement Upstream-First `create_category` service, `POST /categories`, and FastMCP tool.
- [ ] **Category Update**: Implement Upstream-First `update_category` service, `PUT /categories/{id}`, and FastMCP tool.
- [ ] **Category Deletion**: Implement Upstream-First `delete_category` service, `DELETE /categories/{id}`, and FastMCP tool.
- [ ] **Manual Account Creation**: Implement Upstream-First `create_manual_account` service, `POST /accounts/manual`, and FastMCP tool.
- [ ] **Manual Account Update**: Implement Upstream-First `update_manual_account` service, `PUT /accounts/manual/{id}`, and FastMCP tool.
- [ ] **Manual Account Deletion**: Implement Upstream-First `delete_manual_account` service, `DELETE /accounts/manual/{id}`, and FastMCP tool.
- [ ] **Plaid Fetch Trigger**: Implement `trigger_plaid_fetch` service, `POST /accounts/plaid/sync`, and FastMCP tool.
- [ ] **Test Suite**: Add unit and integration tests in `tests/test_category_account_mutations.py`.

---

### 💳 Sprint 3: Transaction Mutations, Grouping, Splitting & Attachments

_Reference Spec_: [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md#sprint-3-transaction-mutations-grouping-splitting--attachments)

- [ ] **Single Transaction Insert**: Implement `create_transactions` (`POST /transactions`).
- [ ] **Bulk Transaction Update**: Implement `bulk_update_transactions` (`PUT /transactions`).
- [ ] **Bulk Transaction Delete**: Implement `bulk_delete_transactions` (`DELETE /transactions`).
- [ ] **Single Transaction Update**: Implement `update_transaction` (`PUT /transactions/{id}`).
- [ ] **Single Transaction Delete**: Implement `delete_transaction` (`DELETE /transactions/{id}`).
- [ ] **Transaction Grouping**: Implement `group_transactions` (`POST /transactions/group`) and `ungroup_transactions` (`DELETE /transactions/group/{id}`).
- [ ] **Transaction Splitting**: Implement `split_transaction` (`POST /transactions/split/{id}`) and `unsplit_transaction` (`DELETE /transactions/split/{id}`).
- [ ] **Transaction Attachments**: Implement attachment upload (`POST /transactions/{id}/attachments`), download (`GET /transactions/attachments/{file_id}`), and delete (`DELETE /transactions/attachments/{file_id}`).
- [ ] **Test Suite**: Add comprehensive test suite in `tests/test_transaction_mutations.py`.

---

### 📊 Sprint 4: Budgets & Time-Series Spending Trends

_Reference Spec_: [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md#sprint-4-budgets--spending-trends)

- [ ] **Budget Settings**: Implement `fetch_budget_settings`, `GET /budgets/settings`, and `get_budget_settings` tool.
- [ ] **Budget Upsert**: Implement `set_budget_value`, `PUT /budgets`, and `upsert_budget` tool.
- [ ] **Budget Clear**: Implement `clear_budget_value`, `DELETE /budgets`, and `clear_budget` tool.
- [ ] **Spending Trends Analysis**: Implement `fetch_spending_trends` (daily/weekly/monthly time-series aggregation), `GET /spending/trends`, and `get_spending_trends` tool.
- [ ] **Test Suite**: Add test suite in `tests/test_budgets_trends.py`.

---

### 🛡️ Sprint 5: Production Security, MCP Primitives & CI/CD

_Reference Spec_: [`docs/MCP_GUIDE.md`](MCP_GUIDE.md) & [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md#sprint-5-production-security--cicd)

- [ ] **API Key Guard**: Implement `verify_api_key` middleware in [`src/lunchmoney_mcp/app/auth.py`](../src/lunchmoney_mcp/app/auth.py).
- [ ] **MCP Executable Entrypoint**: Add `lunchmoney-mcp = "lunchmoney_mcp.mcp.server:main"` script in `pyproject.toml`.
- [ ] **MCP Multi-Transport**: Support `--sse` transport flag in `mcp.run()`.
- [ ] **MCP Resources**: Register `lunchmoney://summary` and `lunchmoney://categories` resources in [`src/lunchmoney_mcp/mcp/server.py`](../src/lunchmoney_mcp/mcp/server.py).
- [ ] **MCP Prompts**: Register `budget_health_check` and `uncategorized_transactions_audit` prompts.
- [x] **GitHub Actions CI**: Add `.github/workflows/ci.yaml` running `task lint`, `task check`, `task test`, and `docker build`.

---

## 📝 Documentation Auto-Improvement Protocol

Whenever an agent completes a task, refactor code, or modify a signature:

1. Update docstrings on touched functions, classes, and modules (NumPy format).
2. Check off completed items in this document (`docs/CHECKLIST.md`).
3. If new APIs, parameters, or edge cases are added, update the relevant specification in `docs/ROADMAP.md` or `docs/AGENT_HANDOFF.md`.
