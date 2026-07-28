"""
FastAPI application for Lunch Money MCP.
"""

import datetime
import logging
from typing import Annotated

from fastapi import Depends, FastAPI
from fastmcp import FastMCP
from sqlmodel import col, select

from lunchmoney_mcp.app.dependencies import (
    get_database,
    get_db_session,
    get_lunchmoney_app,
)
from lunchmoney_mcp.app.lifespan import lifespan
from lunchmoney_mcp.app.sync import sync_database
from lunchmoney_mcp.client import LunchMoneyApp, SyncSummary
from lunchmoney_mcp.database import LunchMoneyDatabase, run_migrations
from lunchmoney_mcp.database.models import (
    Category,
    ManualAccount,
    PlaidAccount,
    Transaction,
    User,
)
from lunchmoney_mcp.schemas import (
    AccountInfo,
    AccountsSummary,
    CategoryInfo,
    RootResponse,
    SyncDetails,
    SyncResponse,
    TransactionInfo,
    UserInfo,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Lunch Money MCP",
    description="Lunch Money Model Context Protocol Server & API",
    lifespan=lifespan,
)


@app.get(path="/", response_model=RootResponse)
async def root() -> RootResponse:
    """Root endpoint returning status message."""
    return RootResponse(message="Hello World")


@app.post(path="/sync", response_model=SyncResponse)
async def sync(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    days: int = 30,
) -> SyncResponse:
    """Run database migrations and synchronize Lunch Money data for specified date window."""
    logger.info("Triggering database migrations and %s-day sync...", days)
    await run_migrations()
    summary: SyncSummary = await sync_database(db=db, client=client, days=days)
    return SyncResponse(
        message="Synchronization complete",
        synced=SyncDetails(
            user=summary.user,
            plaid_accounts=summary.plaid_accounts,
            manual_accounts=summary.manual_accounts,
            categories=summary.categories,
            tags=summary.tags,
            transactions=summary.transactions,
            total=summary.total,
        ),
    )


@app.get(path="/user", response_model=UserInfo | None)
async def get_user_info(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> UserInfo | None:
    """Fetch the authenticated user profile and budget details."""
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


@app.get(path="/categories", response_model=list[CategoryInfo])
async def list_categories(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> list[CategoryInfo]:
    """List all budget categories and subcategories."""
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


@app.get(path="/accounts", response_model=AccountsSummary)
async def list_accounts(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> AccountsSummary:
    """List all connected Plaid and manual accounts with current balances."""
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


@app.get(path="/transactions", response_model=list[TransactionInfo])
async def get_recent_transactions(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    days: int = 30,
    limit: int = 50,
) -> list[TransactionInfo]:
    """
    Fetch recent transactions from local database within specified date window.
    """
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


mcp: FastMCP[None] = FastMCP.from_fastapi(app=app)
fastapi_app = app

__all__: list[str] = [
    "app",
    "fastapi_app",
    "get_database",
    "get_db_session",
    "get_lunchmoney_app",
    "lifespan",
    "mcp",
    "run_migrations",
    "sync_database",
]

if __name__ == "__main__":
    mcp.run()
