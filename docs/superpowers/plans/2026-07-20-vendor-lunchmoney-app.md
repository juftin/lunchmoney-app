# Vendor Lunch Money App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vendor the upstream Lunch Money app module and allow callers to opt out of writing fetched results to `LunchMoneyApp.data`.

**Architecture:** Copy the upstream module into the package unchanged except for its public refresh APIs. `refresh`, `refresh_data`, and `refresh_transactions` accept a keyword-only-compatible `cache: bool = True`; with `False`, they return fetched data without assigning or updating the matching `LunchableData` attribute.

**Tech Stack:** Python 3.13, asyncio, pytest, lunchmoney-python-async.

## Global Constraints

- Copy `clients/python-async/lunchmoney/app.py` from the supplied `app` branch into `src/lunchmoney_mcp/app.py`.
- Preserve existing default behavior with `cache=True`.
- `cache=False` must not mutate `LunchMoneyApp.data`.
- Retain the existing `lunchmoney-python-async` dependency.

---

### Task 1: Vendor the upstream application module

**Files:**
- Create: `src/lunchmoney_mcp/app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Produces: `LunchMoneyApp`, `LunchableData`, and `LunchableClient` exported from `lunchmoney_mcp.app`.

- [ ] **Step 1: Write the failing import test**

```python
def test_vendored_app_exports_lunch_money_app() -> None:
    from lunchmoney_mcp.app import LunchMoneyApp

    assert LunchMoneyApp.__name__ == "LunchMoneyApp"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_app.py::test_vendored_app_exports_lunch_money_app -v`
Expected: FAIL because `lunchmoney_mcp.app` does not exist.

- [ ] **Step 3: Add the upstream module**

Copy the supplied upstream `app.py` to `src/lunchmoney_mcp/app.py`, preserving imports, type annotations, and exports.

- [ ] **Step 4: Run the import test to verify it passes**

Run: `uv run pytest tests/test_app.py::test_vendored_app_exports_lunch_money_app -v`
Expected: PASS.

### Task 2: Support non-caching refreshes

**Files:**
- Modify: `src/lunchmoney_mcp/app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `LunchMoneyApp.refresh`, `LunchMoneyApp.refresh_data`, and `LunchMoneyApp.refresh_transactions`.
- Produces: `cache: bool = True` on each refresh API.

- [ ] **Step 1: Write failing cache-control tests**

```python
@pytest.mark.asyncio
async def test_refresh_without_cache_does_not_replace_data() -> None:
    app = object.__new__(LunchMoneyApp)
    app.data = LunchableData()
    # Configure the model mapper to return a known category response.
    result = await app.refresh(CategoryObject, cache=False)
    assert result
    assert app.data.categories == {}


@pytest.mark.asyncio
async def test_refresh_transactions_without_cache_does_not_update_data() -> None:
    app = object.__new__(LunchMoneyApp)
    app.data = LunchableData()
    # Stub pagination with one known transaction.
    result = await app.refresh_transactions(cache=False)
    assert result
    assert app.data.transactions == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_app.py -v`
Expected: FAIL because the refresh APIs do not accept `cache` and write to `app.data` unconditionally.

- [ ] **Step 3: Add cache controls**

Add `cache: bool = True` to `refresh`, `refresh_data`, and `refresh_transactions`. Guard `self.data.user = user`, `self.data.transactions.update(transaction_map)`, and `setattr(self.data, mapper.data_attr, data_dict)` with `if cache:`. When caching a non-transaction model, return `data_dict` rather than reading it back from `self.data`. Forward `cache` from `refresh_data` to every `refresh` call.

- [ ] **Step 4: Run the cache tests to verify they pass**

Run: `uv run pytest tests/test_app.py -v`
Expected: PASS.

- [ ] **Step 5: Run full verification**

Run: `uv run ruff check src tests && uv run ty check && uv run pytest -v`
Expected: all commands exit zero.
