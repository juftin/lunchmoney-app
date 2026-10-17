---
name: lunchmoney-transaction-review
description: >-
    Review unreviewed Lunch Money transactions using the review_transactions MCP tool.
    Inspects Plaid metadata, counterparties, and account context to recommend cleaned payees,
    accurate categories (preferring specific child categories over parent groups), and descriptive notes,
    scans and matches existing actual recurring items, and applies confirmed updates in bulk.
---

# Lunch Money Transaction Review

Use this skill to fetch unreviewed transactions, generate recommendations, match actual recurring items, handle user adjustments, and apply confirmed changes.

## Workflow

### 1. Fetch Review Workspace & Actual Recurring Items

1. Retrieve the unreviewed queue, active categories, and accounts:
    ```json
    call_mcp_tool(
      ServerName="lunchmoney",
      ToolName="review_transactions",
      Arguments={"query": {"days": 45}}
    )
    ```
2. Retrieve only actual confirmed recurring items (omitting system suggestions):
    ```json
    call_mcp_tool(
      ServerName="lunchmoney",
      ToolName="list_recurring_items",
      Arguments={"include_suggested": false}
    )
    ```

### 2. Process Data with the Fast Local Helper

Run the local parsing script on the tool outputs to normalize payees, match leaf categories, match against actual recurring items, and prepare the update payload:

```bash
python3 ~/.gemini/config/skills/lunchmoney-transaction-review/scripts/process_review.py \
  <path_to_review_transactions_output.txt> \
  /tmp/lunchmoney_pending_updates.json \
  <path_to_recurring_items_output.txt>
```

### 3. Categorization & Payee Rules

- **Prefer Child Categories**: Always recommend leaf/child categories instead of parent groups (`is_group=true`).
    - Example: Under **Dining**, choose `Restaurants` (`378374`), `Takeout` (`2072178`), or `Food Delivery` (`378370`).
    - Example: Under **Income**, choose `Salary` (`378379`), `Bonus` (`3095487`), or `Gift Income` (`386203`).
    - Example: Under **Family**, choose `Kids` (`1071530`), `Childcare` (`2746327`), or `Home` (`378371`).
- **Payee Cleanup**:
    - Strip processor/terminal prefixes (`TST*`, `PY *`, `SQ *`, `AMAZON MKTPL*`).
    - Ignore payment terminal counterparties (`Toast`, `Square`) and prioritize the true merchant entity.
    - Normalize payroll descriptors to clean employer names (e.g. _Smarter Technologies_, _Unstructured_).
- **Special Types & Notes**:
    - Credit Card Payments $\rightarrow$ `Payment, Transfer` with note `Credit Card Payment`.
    - Investment Dividends/Reinvestments $\rightarrow$ `Bank Fees` with note `Dividend` / `Reinvestment`.
    - Refunds $\rightarrow$ original merchant category with note `Refund`.

### 4. Present Table & Matched Actual Recurring Items

Present the generated Markdown table to the user for review.

If any unreviewed transactions match **actual confirmed recurring items** in the user's account, display them in a **🔄 Matched Actual Recurring Items** section and ask:

> _"Would you like to link any of these transactions to their matching recurring item (`recurring_id`)?"_

> **Important**: Do not apply any changes until the user explicitly confirms or adjusts the recommendations.

### 5. Handle User Feedback & Refinements

If the user provides feedback (e.g. _"Mendocino and Chipotle are takeout"_, _"Link student loan to recurring item 302102"_):

1. Resolve the requested merchant/transaction IDs, categories, or `recurring_id` links.
2. Update the prepared update list.
3. Re-present the adjusted rows or updated table to confirm alignment.

### 6. Apply Confirmed Updates

Once the user confirms the final set of changes, call `bulk_update_transactions`:

```json
call_mcp_tool(
  ServerName="lunchmoney",
  ToolName="bulk_update_transactions",
  Arguments={
    "transactions": [
      {
        "id": 123456,
        "payee": "Clean Name",
        "category_id": 378374,
        "notes": "Dinner",
        "recurring_id": 302102,
        "status": "reviewed"
      }
    ]
  }
)
```

### 7. Report Results

Report the number of updated transactions and confirm their new `reviewed` status.
