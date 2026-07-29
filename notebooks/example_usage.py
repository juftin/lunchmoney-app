import marimo

__generated_with = "0.23.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    # 💰 Lunch Money MCP - Example Usage Notebook

    This notebook demonstrates how to interact with **Lunch Money MCP** service functions, database records, and FastMCP tools.
    """)
    return


@app.cell
def _():
    from lunchmoney_mcp.client import LunchMoneyApp
    from lunchmoney_mcp.database import LunchMoneyDatabase
    from lunchmoney_mcp.services import (
        execute_sync,
        fetch_accounts,
        fetch_recent_transactions,
        fetch_user_info,
    )

    return (
        LunchMoneyApp,
        LunchMoneyDatabase,
        execute_sync,
        fetch_accounts,
        fetch_recent_transactions,
        fetch_user_info,
    )


@app.cell
def _(LunchMoneyApp, LunchMoneyDatabase):
    db = LunchMoneyDatabase()
    client = LunchMoneyApp(cache=False)
    return client, db


@app.cell
def _(mo):
    days_slider = mo.ui.slider(
        start=7, stop=90, step=1, value=30, label="Sync Window (Days)"
    )
    days_slider
    return (days_slider,)


@app.cell
async def _(client, days_slider, db, execute_sync):
    sync_result = await execute_sync(db=db, client=client, days=days_slider.value)
    return (sync_result,)


@app.cell(hide_code=True)
def _(mo, sync_result):
    mo.md(f"""
    ### 🔄 Database Sync Summary

    - **Status:** `{sync_result.message}`
    - **Total Records Synced:** `{sync_result.synced.total}`
    - **User Records:** `{sync_result.synced.user}`
    - **Plaid Accounts:** `{sync_result.synced.plaid_accounts}`
    - **Manual Accounts:** `{sync_result.synced.manual_accounts}`
    - **Categories:** `{sync_result.synced.categories}`
    - **Transactions:** `{sync_result.synced.transactions}`
    """)
    return


@app.cell
async def _(db, fetch_user_info):
    user_info = await fetch_user_info(db=db)
    return (user_info,)


@app.cell(hide_code=True)
def _(mo, user_info):
    if user_info:
        user_md = mo.md(
            f"""
            ### 👤 User Profile
            - **Name:** {user_info.name}
            - **Email:** {user_info.email}
            - **Budget:** {user_info.budget_name}
            - **Currency:** {user_info.primary_currency.upper()}
            """
        )
    else:
        user_md = mo.md("_No user profile synced yet._")
    user_md
    return


@app.cell
async def _(db, fetch_accounts):
    accounts = await fetch_accounts(db=db)
    return (accounts,)


@app.cell(hide_code=True)
def _(accounts, mo):
    plaid_data = [a.model_dump() for a in accounts.plaid_accounts]

    mo.md(
        f"""
        ### 🏦 Accounts Overview
        **Plaid Accounts ({len(plaid_data)}):**
        """
    )
    return (plaid_data,)


@app.cell
def _(mo, plaid_data):
    mo.ui.table(plaid_data)
    return


@app.cell
async def _(days_slider, db, fetch_recent_transactions):
    txns = await fetch_recent_transactions(db=db, days=days_slider.value, limit=25)
    return (txns,)


@app.cell(hide_code=True)
def _(mo, txns):
    txn_data = [t.model_dump() for t in txns]
    mo.md(
        f"""
        ### 💳 Recent Transactions (Last {len(txn_data)} items)
        """
    )
    return (txn_data,)


@app.cell
def _(mo, txn_data):
    mo.ui.table(txn_data)
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
