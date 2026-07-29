"""Service logic for Accounts data operations."""

from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import ManualAccount, PlaidAccount
from lunchmoney_mcp.schemas import AccountInfo, AccountsSummary


async def fetch_accounts(db: LunchMoneyDatabase) -> AccountsSummary:
    """Fetch all connected Plaid and manual accounts with current balances.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    AccountsSummary
        Combined summary of connected Plaid and manual accounts.
    """
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


async def fetch_manual_account_by_id(
    db: LunchMoneyDatabase,
    account_id: int,
) -> AccountInfo | None:
    """Fetch one synchronized manual account by identifier.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    account_id : int
        Identifier of the manual account to retrieve.

    Returns
    -------
    AccountInfo | None
        Matching manual account, or ``None`` when it has not been synchronized.
    """
    account = await db.get(ManualAccount, account_id)
    if account is None:
        return None
    return AccountInfo(
        id=account.id,
        name=account.name,
        balance=float(account.balance),
        currency=account.currency,
        type_or_status=account.type,
        institution_name=account.institution_name,
    )


async def fetch_plaid_account_by_id(
    db: LunchMoneyDatabase,
    account_id: int,
) -> AccountInfo | None:
    """Fetch one synchronized Plaid account by identifier.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    account_id : int
        Identifier of the Plaid account to retrieve.

    Returns
    -------
    AccountInfo | None
        Matching Plaid account, or ``None`` when it has not been synchronized.
    """
    account = await db.get(PlaidAccount, account_id)
    if account is None:
        return None
    return AccountInfo(
        id=account.id,
        name=account.name,
        balance=float(account.balance),
        currency=account.currency,
        type_or_status=account.status,
        institution_name=account.institution_name,
    )
