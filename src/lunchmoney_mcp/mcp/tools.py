"""
MCP Tools and Resources registration for Lunch Money operations.
"""

import datetime
from typing import Any

from fastmcp import FastMCP
from sqlmodel import col, select

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


def register_mcp_tools(mcp: FastMCP[Any]) -> None:
    """Register Lunch Money MCP tools and resources on FastMCP server instance."""

    @mcp.tool()
    async def sync_data(days: int = 30) -> dict[str, Any]:
        """
        Synchronize transactions, accounts, categories, and tags from Lunch Money API.

        Parameters
        ----------
        days: int
            Number of days back from today to synchronize. Default is 30.
        """
        await run_migrations()
        db = get_database()
        client = get_lunchmoney_app()
        summary = await sync_database(db=db, client=client, days=days)
        return {
            "status": "success",
            "synced_records": summary,
        }

    @mcp.tool()
    async def get_user_info() -> dict[str, Any] | None:
        """Fetch the authenticated user profile and budget details from database."""
        db = get_database()
        async with db.session() as session:
            result = await session.exec(select(User))
            user = result.first()
            if user is None:
                return None
            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "budget_name": user.budget_name,
                "primary_currency": user.primary_currency,
            }

    @mcp.tool()
    async def list_categories() -> list[dict[str, Any]]:
        """List all budget categories and subcategories from database."""
        db = get_database()
        categories = await db.list(Category)
        return [
            {
                "id": c.id,
                "name": c.name,
                "is_income": c.is_income,
                "exclude_from_budget": c.exclude_from_budget,
                "exclude_from_totals": c.exclude_from_totals,
                "is_group": c.is_group,
                "group_id": c.group_id,
            }
            for c in categories
        ]

    @mcp.tool()
    async def list_accounts() -> dict[str, Any]:
        """List all connected Plaid and manual accounts with current balances."""
        db = get_database()
        plaid_accs = await db.list(PlaidAccount)
        manual_accs = await db.list(ManualAccount)
        return {
            "plaid_accounts": [
                {
                    "id": a.id,
                    "name": a.name,
                    "institution_name": a.institution_name,
                    "balance": a.balance,
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
                    "balance": a.balance,
                    "currency": a.currency,
                }
                for a in manual_accs
            ],
        }

    @mcp.tool()
    async def get_recent_transactions(
        days: int = 30, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Fetch recent transactions from local database within specified date window.

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
            return [
                {
                    "id": t.id,
                    "date": t.var_date.isoformat(),
                    "payee": t.payee,
                    "amount": float(t.amount),
                    "currency": t.currency,
                    "category_id": t.category_id,
                    "notes": t.notes,
                    "status": t.status,
                }
                for t in txns
            ]
