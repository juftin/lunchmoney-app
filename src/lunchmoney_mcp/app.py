"""
FastAPI application for Lunch Money MCP.
"""

import datetime
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cache
from typing import Annotated, Any

from fastapi import Depends, FastAPI
from fastmcp import FastMCP
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.utilities.lifespan import combine_lifespans
from filelock import FileLock, Timeout
from filelock._soft import SoftFileLock
from lunchmoney.models.transaction_object import TransactionObject
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from lunchmoney_mcp.client import (
    CategoryObject,
    LunchMoneyApp,
    ManualAccountObject,
    PlaidAccountObject,
    SyncSummary,
    TagObject,
    UserObject,
)
from lunchmoney_mcp.database import LunchMoneyDatabase, run_migrations
from lunchmoney_mcp.database.models import (
    Category,
    ManualAccount,
    PlaidAccount,
    Tag,
    Transaction,
    User,
)

logger = logging.getLogger(__name__)


@cache
def get_database() -> LunchMoneyDatabase:
    """FastAPI dependency supplying the shared LunchMoneyDatabase instance."""
    return LunchMoneyDatabase()


async def get_db_session(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped AsyncSession."""
    async with db.session() as session:
        yield session


def get_lunchmoney_app() -> LunchMoneyApp:
    """FastAPI dependency supplying a LunchMoneyApp client instance."""
    return LunchMoneyApp(cache=False)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI application lifespan running single-worker database migrations."""
    lock: SoftFileLock = FileLock(lock_file=".lunchmoney_migration.lock", timeout=0)
    try:
        with lock:
            logger.info(
                "Worker acquired startup lock. Executing database migrations..."
            )
            await run_migrations()
    except Timeout:
        logger.debug(
            "Worker process skipped startup database migrations (lock held by another worker)."
        )

    yield
    if get_database.cache_info().currsize > 0:
        db: LunchMoneyDatabase = get_database()
        await db.dispose()
        get_database.cache_clear()


async def sync_database(
    db: LunchMoneyDatabase,
    client: LunchMoneyApp,
    days: int = 30,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> SyncSummary:
    """
    Populate or synchronize the database for a given date range.

    Parameters
    ----------
    db: LunchMoneyDatabase
        Database instance for executing graph upserts.
    client: LunchMoneyApp
        LunchMoney API client instance.
    days: int
        Number of days back from end_date if start_date is omitted. Default 30.
    start_date: datetime.date | None
        Start date for transactions query. Defaults to end_date - timedelta(days=days).
    end_date: datetime.date | None
        End date for transactions query. Defaults to current date.

    Returns
    -------
    SyncSummary
        Counts of records persisted across categories, accounts, tags, user, and transactions.
    """
    resolved_end_date: datetime.date = end_date or datetime.date.today()
    resolved_start_date = (
        start_date
        if start_date is not None
        else resolved_end_date - datetime.timedelta(days=days)
    )
    user_obj: UserObject = await client.refresh(model=UserObject)
    plaid_objs: dict[int, PlaidAccountObject] = await client.refresh(
        model=PlaidAccountObject
    )
    manual_objs: dict[int, ManualAccountObject] = await client.refresh(
        model=ManualAccountObject
    )
    category_objs: dict[int, CategoryObject] = await client.refresh(
        model=CategoryObject
    )
    tag_objs: dict[int, TagObject] = await client.refresh(model=TagObject)
    transaction_objs: dict[int, TransactionObject] = await client.refresh_transactions(
        start_date=resolved_start_date,
        end_date=resolved_end_date,
        cache=False,
    )

    records: list[SQLModel] = []
    records.append(User.from_api(model=user_obj))
    for plaid in plaid_objs.values():
        records.append(PlaidAccount.from_api(model=plaid))
    for manual in manual_objs.values():
        records.append(ManualAccount.from_api(model=manual))
    for category in category_objs.values():
        records.append(Category.from_api(model=category))
    for tag in tag_objs.values():
        records.append(Tag.from_api(model=tag))
    for txn in transaction_objs.values():
        records.append(Transaction.from_api(model=txn))

    await db.upsert_many(records)

    return SyncSummary(
        user=1 if user_obj else 0,
        plaid_accounts=len(plaid_objs),
        manual_accounts=len(manual_objs),
        categories=len(category_objs),
        tags=len(tag_objs),
        transactions=len(transaction_objs),
    )


fastapi_app = FastAPI(
    title="Lunch Money MCP",
    description="Lunch Money Model Context Protocol Server & API",
    lifespan=lifespan,
)


@fastapi_app.get(path="/")
async def root() -> dict[str, object]:
    """Root endpoint returning Hello World."""
    return {
        "message": "Hello World",
    }


@fastapi_app.post(path="/sync")
async def sync(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    app: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    days: int = 30,
) -> dict[str, object]:
    """Run database migrations and synchronize Lunch Money data for specified date window."""
    logger.info("Triggering database migrations and %s-day sync...", days)
    await run_migrations()
    summary: SyncSummary = await sync_database(db=db, client=app, days=days)
    return {
        "message": "Synchronization complete",
        "synced": summary,
    }


mcp: FastMCP[Any] = FastMCP.from_fastapi(app=fastapi_app)
mcp_app: StarletteWithLifespan = mcp.http_app(path="/mcp")
app = FastAPI(
    routes=[
        *mcp_app.routes,
        *fastapi_app.routes,
    ],
    lifespan=combine_lifespans(mcp_app.lifespan, lifespan),
)

__all__: list[str] = ["app", "mcp"]

if __name__ == "__main__":
    mcp.run()
