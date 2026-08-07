"""
Database synchronization services for Lunch Money data.
"""

import datetime

from lunchmoney.models.transaction_object import TransactionObject
from sqlmodel import SQLModel

from lunchmoney_mcp.client import (
    CategoryObject,
    LunchMoneyApp,
    ManualAccountObject,
    PlaidAccountObject,
    SyncSummary,
    TagObject,
    UserObject,
)
from lunchmoney_mcp.config import get_settings
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import (
    Category,
    ManualAccount,
    PlaidAccount,
    SyncMetadata,
    Tag,
    Transaction,
    User,
)


async def sync_database(
    db: LunchMoneyDatabase,
    client: LunchMoneyApp,
    days: int = 30,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    incremental: bool = False,
    safety_margin_minutes: int | None = None,
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
    incremental : bool
        Whether to resume transaction sync from its successful watermark.
    safety_margin_minutes : int | None
        Optional overlap override subtracted from an existing watermark.

    Returns
    -------
    SyncSummary
        Counts of records persisted across categories, accounts, tags, user, and transactions.
    """
    sync_started_at = datetime.datetime.now(datetime.timezone.utc)
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
    transaction_watermark = (
        await db.get_sync_metadata("transactions") if incremental else None
    )
    if transaction_watermark is not None:
        resolved_margin = (
            safety_margin_minutes
            if safety_margin_minutes is not None
            else get_settings().sync_safety_margin_minutes
        )
        transaction_objs: dict[
            int, TransactionObject
        ] = await client.refresh_transactions(
            updated_since=transaction_watermark.last_synced_at
            - datetime.timedelta(minutes=resolved_margin),
            cache=False,
        )
    else:
        transaction_objs = await client.refresh_transactions(
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
    await db.upsert_sync_metadata(
        SyncMetadata(
            domain="metadata",
            last_synced_at=sync_started_at,
        )
    )
    if incremental:
        await db.upsert_sync_metadata(
            SyncMetadata(
                domain="transactions",
                last_synced_at=sync_started_at,
            )
        )

    return SyncSummary(
        user=1 if user_obj else 0,
        plaid_accounts=len(plaid_objs),
        manual_accounts=len(manual_objs),
        categories=len(category_objs),
        tags=len(tag_objs),
        transactions=len(transaction_objs),
    )


__all__ = ["sync_database"]
