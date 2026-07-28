"""
FastMCP server instance and tool definitions for Lunch Money operations.
"""

import datetime

from fastmcp import FastMCP
from pydantic import BaseModel, Field
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

mcp = FastMCP("Lunch Money MCP")


class UserInfo(BaseModel):
    """User profile details."""

    id: int
    name: str
    email: str
    budget_name: str
    primary_currency: str


class CategoryInfo(BaseModel):
    """Budget category details."""

    id: int
    name: str
    is_income: bool
    exclude_from_budget: bool
    exclude_from_totals: bool
    is_group: bool
    group_id: int | None = None


class AccountInfo(BaseModel):
    """Financial account details."""

    id: int
    name: str
    balance: float
    currency: str
    type_or_status: str | None = None
    institution_name: str | None = None


class AccountsSummary(BaseModel):
    """Connected Plaid and manual accounts."""

    plaid_accounts: list[AccountInfo] = Field(default_factory=list)
    manual_accounts: list[AccountInfo] = Field(default_factory=list)


class TransactionInfo(BaseModel):
    """Transaction summary item."""

    id: int
    date: datetime.date
    payee: str
    amount: float
    currency: str
    category_id: int | None = None
    notes: str | None = None
    status: str


class SyncResult(BaseModel):
    """Synchronization outcome details."""

    status: str
    user: int
    plaid_accounts: int
    manual_accounts: int
    categories: int
    tags: int
    transactions: int
    total: int


@mcp.tool()
async def sync_data(days: int = 30) -> SyncResult:
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
    return SyncResult(
        status="success",
        user=summary.user,
        plaid_accounts=summary.plaid_accounts,
        manual_accounts=summary.manual_accounts,
        categories=summary.categories,
        tags=summary.tags,
        transactions=summary.transactions,
        total=summary.total,
    )


@mcp.tool()
async def get_user_info() -> UserInfo | None:
    """Fetch the authenticated user profile and budget details."""
    db = get_database()
    async with db.session() as session:
        result = await session.exec(select(User))
        user = result.first()
        if user is None:
            return None
        return UserInfo(
            id=user.id,
            name=user.name,
            email=user.email,
            budget_name=user.budget_name,
            primary_currency=user.primary_currency,
        )


@mcp.tool()
async def list_categories() -> list[CategoryInfo]:
    """List all budget categories and subcategories."""
    db = get_database()
    categories = await db.list(Category)
    return [
        CategoryInfo(
            id=c.id,
            name=c.name,
            is_income=c.is_income,
            exclude_from_budget=c.exclude_from_budget,
            exclude_from_totals=c.exclude_from_totals,
            is_group=c.is_group,
            group_id=c.group_id,
        )
        for c in categories
    ]


@mcp.tool()
async def list_accounts() -> AccountsSummary:
    """List all connected Plaid and manual accounts with current balances."""
    db = get_database()
    plaid_accs = await db.list(PlaidAccount)
    manual_accs = await db.list(ManualAccount)
    return AccountsSummary(
        plaid_accounts=[
            AccountInfo(
                id=a.id,
                name=a.name,
                institution_name=a.institution_name,
                balance=float(a.balance),
                currency=a.currency,
                type_or_status=a.status,
            )
            for a in plaid_accs
        ],
        manual_accounts=[
            AccountInfo(
                id=a.id,
                name=a.name,
                balance=float(a.balance),
                currency=a.currency,
                type_or_status=a.type,
            )
            for a in manual_accs
        ],
    )


@mcp.tool()
async def get_recent_transactions(
    days: int = 30, limit: int = 50
) -> list[TransactionInfo]:
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
            TransactionInfo(
                id=t.id,
                date=t.var_date,
                payee=t.payee,
                amount=float(t.amount),
                currency=t.currency,
                category_id=t.category_id,
                notes=t.notes,
                status=t.status,
            )
            for t in txns
        ]


__all__ = [
    "AccountInfo",
    "AccountsSummary",
    "CategoryInfo",
    "SyncResult",
    "TransactionInfo",
    "UserInfo",
    "get_recent_transactions",
    "get_user_info",
    "list_accounts",
    "list_categories",
    "mcp",
    "sync_data",
]
