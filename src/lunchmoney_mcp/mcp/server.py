"""
FastMCP server instance and tool definitions for Lunch Money operations.
"""

import datetime

from fastmcp import FastMCP
from sqlmodel import col, select
import toons

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.app.sync import sync_database
from lunchmoney_mcp.database import run_migrations
from lunchmoney_mcp.database.models import (
    Category,
    ManualAccount,
    PlaidAccount,
    Transaction,
    User,
)

mcp = FastMCP("Lunch Money MCP")


@mcp.tool()
async def sync_data(days: int = 30) -> str:
    """
    Synchronize transactions, accounts, categories, and tags from Lunch Money API.
    Returns results encoded in Token-Oriented Object Notation (TOON).

    Parameters
    ----------
    days: int
        Number of days back from today to synchronize. Default is 30.
    """
    await run_migrations()
    db = get_database()
    client = get_lunchmoney_app()
    summary = await sync_database(db=db, client=client, days=days)
    data = {
        "status": "success",
        "synced_records": {
            "user": summary.user,
            "plaid_accounts": summary.plaid_accounts,
            "manual_accounts": summary.manual_accounts,
            "categories": summary.categories,
            "tags": summary.tags,
            "transactions": summary.transactions,
            "total": summary.total,
        },
    }
    return toons.dumps(data)


@mcp.tool()
async def get_user_info() -> str:
    """Fetch the authenticated user profile and budget details encoded in TOON format."""
    db = get_database()
    async with db.session() as session:
        result = await session.exec(select(User))
        user = result.first()
        if user is None:
            return toons.dumps({})
        data = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "budget_name": user.budget_name,
            "primary_currency": user.primary_currency,
        }
        return toons.dumps(data)


@mcp.tool()
async def list_categories() -> str:
    """List all budget categories and subcategories encoded in TOON format."""
    db = get_database()
    categories = await db.list(Category)
    data = [
        {
            "id": c.id,
            "name": c.name,
            "is_income": c.is_income,
            "exclude_from_budget": c.exclude_from_budget,
            "exclude_from_totals": c.exclude_from_totals,
            "is_group": c.is_group,
            "group_id": c.group_id or 0,
        }
        for c in categories
    ]
    return toons.dumps(data)


@mcp.tool()
async def list_accounts() -> str:
    """List all connected Plaid and manual accounts encoded in TOON format."""
    db = get_database()
    plaid_accs = await db.list(PlaidAccount)
    manual_accs = await db.list(ManualAccount)
    data = {
        "plaid_accounts": [
            {
                "id": a.id,
                "name": a.name,
                "institution_name": a.institution_name or "",
                "balance": float(a.balance),
                "currency": a.currency,
                "status": a.status,
            }
            for a in plaid_accs
        ],
        "manual_accounts": [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "balance": float(a.balance),
                "currency": a.currency,
            }
            for a in manual_accs
        ],
    }
    return toons.dumps(data)


@mcp.tool()
async def get_recent_transactions(days: int = 30, limit: int = 50) -> str:
    """
    Fetch recent transactions from local database encoded in TOON format.

    Parameters
    ----------
    days: int
        Number of days back from today to include. Default 30.
    limit: int
        Maximum number of transactions to return. Default 50.
    """
    db = get_database()
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    async with db.session() as session:
        statement = (
            select(Transaction)
            .where(Transaction.var_date >= cutoff)
            .order_by(col(Transaction.var_date).desc())
            .limit(limit)
        )
        results = await session.exec(statement)
        txns = results.all()
        data = [
            {
                "id": t.id,
                "date": t.var_date.isoformat(),
                "payee": t.payee,
                "amount": float(t.amount),
                "currency": t.currency,
                "category_id": t.category_id or 0,
                "notes": t.notes or "",
                "status": t.status,
            }
            for t in txns
        ]
        return toons.dumps(data)


__all__ = [
    "get_recent_transactions",
    "get_user_info",
    "list_accounts",
    "list_categories",
    "mcp",
    "sync_data",
]
