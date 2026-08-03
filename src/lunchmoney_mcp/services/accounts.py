"""Service logic for Accounts data operations."""

import datetime

from lunchmoney.models import (
    ManualAccountObject,
    PlaidAccountObject,
)

from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import ManualAccount, PlaidAccount, Transaction
from lunchmoney_mcp.schemas import (
    AccountsSummary,
    ManualAccountCreateRequest,
    ManualAccountUpdateRequest,
)

async def fetch_accounts(db: LunchMoneyDatabase) -> AccountsSummary:
    """Fetch complete manual and Plaid account collections in one response.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    AccountsSummary
        Full synchronized account objects separated by their Lunch Money source.
    """
    manual_accounts = await fetch_manual_accounts(db=db)
    plaid_accounts = await fetch_plaid_accounts(db=db)
    return AccountsSummary(
        manual_accounts=manual_accounts,
        plaid_accounts=plaid_accounts,
    )


async def fetch_manual_accounts(
    db: LunchMoneyDatabase,
) -> list[ManualAccountObject]:
    """Fetch all synchronized manual accounts with every upstream field.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    list[ManualAccountObject]
        Complete synchronized manual-account objects.
    """
    return [account.to_api() for account in await db.list(ManualAccount)]


async def fetch_plaid_accounts(
    db: LunchMoneyDatabase,
) -> list[PlaidAccountObject]:
    """Fetch all synchronized Plaid accounts with every upstream field.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    list[PlaidAccountObject]
        Complete synchronized Plaid-account objects.
    """
    return [account.to_api() for account in await db.list(PlaidAccount)]


async def fetch_manual_account_by_id(
    db: LunchMoneyDatabase,
    account_id: int,
) -> ManualAccountObject | None:
    """Fetch one synchronized manual account by identifier.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    account_id : int
        Identifier of the manual account to retrieve.

    Returns
    -------
    ManualAccountObject | None
        Matching manual account, or ``None`` when it has not been synchronized.
    """
    account = await db.get(ManualAccount, account_id)
    if account is None:
        return None
    return account.to_api()


async def fetch_plaid_account_by_id(
    db: LunchMoneyDatabase,
    account_id: int,
) -> PlaidAccountObject | None:
    """Fetch one synchronized Plaid account by identifier.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    account_id : int
        Identifier of the Plaid account to retrieve.

    Returns
    -------
    PlaidAccountObject | None
        Matching Plaid account, or ``None`` when it has not been synchronized.
    """
    account = await db.get(PlaidAccount, account_id)
    if account is None:
        return None
    return account.to_api()


async def _store_manual_account(
    db: LunchMoneyDatabase,
    account: ManualAccountObject,
) -> ManualAccountObject:
    """Persist an upstream manual-account response and preserve all its fields."""
    await db.upsert(ManualAccount.from_api(account))
    return account


async def create_manual_account(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    request: ManualAccountCreateRequest,
) -> ManualAccountObject:
    """Create a manual account upstream before saving its canonical response.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    db : LunchMoneyDatabase
        Database manager that stores the canonical response.
    request : ManualAccountCreateRequest
        Validated manual-account fields supplied by an API or MCP caller.

    Returns
    -------
    ManualAccountObject
        Created manual account after its local cache has been updated.
    """
    account = await client.client.manual_accounts.create_manual_account(
        create_manual_account_request_object=request.to_api(),
    )
    return await _store_manual_account(db=db, account=account)


async def update_manual_account(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    account_id: int,
    request: ManualAccountUpdateRequest,
) -> ManualAccountObject:
    """Update a manual account upstream before saving its canonical response.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    db : LunchMoneyDatabase
        Database manager that stores the canonical response.
    account_id : int
        Identifier of the manual account to update.
    request : ManualAccountUpdateRequest
        Validated fields to update.

    Returns
    -------
    ManualAccountObject
        Updated manual account after its local cache has been updated.
    """
    account = await client.client.manual_accounts.update_manual_account(
        id=account_id,
        update_manual_account_request_object=request.to_api(),
    )
    return await _store_manual_account(db=db, account=account)


async def delete_manual_account(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    account_id: int,
    delete_items: bool | None = None,
    delete_balance_history: bool | None = None,
) -> None:
    """Delete a manual account upstream before removing its cached record.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    db : LunchMoneyDatabase
        Database manager that removes the stale cached row.
    account_id : int
        Identifier of the manual account to delete.
    delete_items : bool | None
        Whether Lunch Money should delete related transactions and rules.
    delete_balance_history : bool | None
        Whether Lunch Money should delete associated balance history.
    """
    await client.client.manual_accounts.delete_manual_account(
        id=account_id,
        delete_items=delete_items,
        delete_balance_history=delete_balance_history,
    )
    transactions = await db.list(Transaction)
    affected_transactions = [
        transaction
        for transaction in transactions
        if transaction.manual_account_id == account_id
    ]
    if delete_items:
        for transaction in affected_transactions:
            await db.delete(Transaction, transaction.id)
    else:
        for transaction in affected_transactions:
            transaction.manual_account_id = None
        if affected_transactions:
            await db.upsert_many(affected_transactions)
    await db.delete(ManualAccount, account_id)


async def trigger_plaid_fetch(
    client: LunchMoneyApp,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    account_id: int | None = None,
) -> None:
    """Ask Lunch Money to fetch recent Plaid transactions.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    start_date : datetime.date | None
        Optional inclusive start of the transaction fetch window.
    end_date : datetime.date | None
        Optional inclusive end of the transaction fetch window.
    account_id : int | None
        Optional Plaid account identifier; omitting it fetches eligible accounts.
    """
    await client.client.plaid.trigger_plaid_account_fetch(
        start_date=start_date,
        end_date=end_date,
        id=account_id,
    )
