---
name: lunchmoney-transaction-review
description: >-
    Pure-prompt skill to review and categorize unreviewed Lunch Money transactions using MCP tools.
    Works entirely in-context without code execution: inspects Plaid metadata, counterparties,
    and account context to recommend cleaned payees, maps transactions to specific child categories,
    matches confirmed actual recurring items, and applies confirmed changes in bulk.
---

# Lunch Money Transaction Review (Pure Prompt / Markdown-Only)

Use this skill in any MCP-enabled assistant (such as Gemini Spark, Claude, or Codex) to inspect unreviewed transactions, generate smart categorization recommendations, match actual recurring items, and apply updates in bulk. No code execution or Python environment is required.

---

## 🛠️ MCP Workflow

### Step 1: Fetch Review Workspace & Actual Recurring Items

Execute these two tool calls:

1. **Fetch the unreviewed workspace**:

    ```json
    call_mcp_tool(
      ServerName="lunchmoney",
      ToolName="review_transactions",
      Arguments={"query": {"days": 45}}
    )
    ```

    _Returns the list of unreviewed `transactions`, user `categories` tree, and account mappings._

2. **Fetch only confirmed recurring items** (omit system guesses):
    ```json
    call_mcp_tool(
      ServerName="lunchmoney",
      ToolName="list_recurring_items",
      Arguments={"include_suggested": false}
    )
    ```

---

## 🧠 In-Context Categorization & Normalization Rules

Analyze the returned JSON objects using the following rules:

### 1. Prefer Specific Child / Leaf Categories

- Inspect the returned `categories` array.
- Ignore category groups (`is_group: true` like _Dining_, _Income_, _Family_).
- Map each transaction to an active child leaf category (`is_group: false` / has a `group_id`):
    - **Fast Food / Takeout** (`FOOD_AND_DRINK_FAST_FOOD` or Chipotle, Mendocino Farms, Acai, delivery services) $\rightarrow$ Choose child `Takeout` or `Food Delivery` if available; otherwise `Restaurants`.
    - **Dine-In / Breweries / Cafes** $\rightarrow$ Choose child `Restaurants`, `Alcohol, Bars`, or `Coffee Shops`.
    - **Groceries** $\rightarrow$ Choose child `Groceries` or `Supermarkets`.
    - **Paycheck / Direct Deposit** (`INCOME_WAGES` or contains `PAYROLL`) $\rightarrow$ Choose child `Salary` or `Wages` under Income.
    - **Kids / Children Stores** $\rightarrow$ Choose child `Kids` or `Childcare`.
    - **Credit Card Payments / Account Transfers** $\rightarrow$ Choose `Payment, Transfer`.
    - **Bank Interest & Investment Dividends** $\rightarrow$ Choose `Bank Fees` or `Investment Income`.

### 2. Clean and Normalize Payee Names

- If the existing `payee` is already clean and readable (e.g. mixed case like _Cerebral Brewing_), keep it.
- If the payee is an all-caps processor string or messy descriptor:
    - Check `plaid_metadata.counterparties` for a high-confidence entity of `type: "merchant"` or `"financial_institution"`.
    - Avoid payment terminal brand names (`Toast`, `Square`, `Clover`) taking over the actual merchant name.
    - Strip processor prefixes: `TST*`, `PY *`, `SQ *`, `POS DEBIT`, `PURCHASE AUTHORIZED ON`, `AMAZON MKTPL*`, `PAYMENT THANK YOU`.
    - Strip web domains and trailing transaction IDs (e.g. `APPLE.COM/US` $\rightarrow$ _Apple_, `*5Q6K570G0`).
    - Format all-caps merchant names into Title Case (e.g. `SAFEWAY` $\rightarrow$ _Safeway_).

### 3. Match Only Actual Recurring Items

- Compare each transaction against the items from `list_recurring_items`:
    - **Strict Amount Check**: Fixed recurring items (subscriptions, insurance, tuition, loans, mortgage) MUST match the expected amount within \$0.01.
    - **Category Isolation**: Never match credit card transfers (`Payment, Transfer`) to loan, mortgage, or bill recurring items (e.g. do not match a Chase credit card payment to a Chase mortgage).
    - **Salary Deposits**: Match confirmed recurring salary items with payroll transactions from the same employer.

---

## 📊 Step 2: Present the Review Table to the User

Output a clean Markdown table summarizing all proposed changes:

```markdown
### Unreviewed Transactions Review (N items)

| ID           | Date       | Account             | Amount  | Raw Payee         | Proposed Payee          | Proposed Child Category | Proposed Notes  |
| :----------- | :--------- | :------------------ | :------ | :---------------- | :---------------------- | :---------------------- | :-------------- |
| `2473094191` | 2026-08-28 | Chase - Sapphire    | $38.24  | Mendocino Farms   | Mendocino Farms         | **Takeout** (`2072178`) | —               |
| `2474733910` | 2026-09-01 | E\*Trade - Checking | $268.94 | DEPT EDUCATION LN | Department of Education | **Bills** (`380602`)    | `Student Loans` |
```

If any recurring item matches were identified:

```markdown
### 🔄 Matched Actual Recurring Items

The following transactions match actual recurring items in your Lunch Money account:

- **Tx `2474733910`** (Department of Education, $268.94) $\rightarrow$ Recurring Item **`302102`** (_Department of Education_, monthly) — _Exact amount & payee match_

_Would you like to link any of these transactions to their recurring item (`recurring_id`)?_
```

> ⚠️ **Safety Guardrail**: Never push changes automatically. Always pause and request user confirmation or adjustments before updating.

---

## ✏️ Step 3: Handle Feedback & Adjustments

When the user gives feedback (e.g. _"Acai Alley is takeout"_, _"Amazon was groceries tip"_, _"Don't review Amazon"_):

1. Update the proposed values (payee, `category_id`, `notes`, or `recurring_id`) for the specified transactions.
2. Confirm the adjustments with the user.

---

## 🚀 Step 4: Apply Confirmed Updates in Bulk

When the user confirms, call `bulk_update_transactions`:

```json
call_mcp_tool(
  ServerName="lunchmoney",
  ToolName="bulk_update_transactions",
  Arguments={
    "request": {
      "transactions": [
        {
          "id": 2473094191,
          "payee": "Mendocino Farms",
          "category_id": 2072178,
          "status": "reviewed"
        },
        {
          "id": 2474733910,
          "payee": "Department of Education",
          "category_id": 380602,
          "notes": "Student Loans",
          "recurring_id": 302102,
          "status": "reviewed"
        }
      ]
    }
  }
)
```

Confirm to the user that the transactions have been updated and marked as `reviewed`.
