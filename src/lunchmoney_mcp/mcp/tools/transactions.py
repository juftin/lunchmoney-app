"""FastMCP tools for transaction queries and upstream-first mutations."""

from typing import TYPE_CHECKING

from lunchmoney.models import (
    CreateNewTransactionsRequest,
    DeleteTransactionsRequest,
    GetTransactionAttachmentUrl200Response,
    GroupTransactionsRequest,
    SplitTransactionRequest,
    TransactionAttachmentObject,
    UpdateTransactionObject,
    UpdateTransactionsRequest,
)

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import TransactionAttachmentUploadRequest, TransactionInfo
from lunchmoney_mcp.services import (
    bulk_delete_transactions as bulk_delete_transactions_service,
    bulk_update_transactions as bulk_update_transactions_service,
    create_transactions as create_transactions_service,
    delete_transaction as delete_transaction_service,
    delete_transaction_attachment as delete_transaction_attachment_service,
    fetch_attachment_by_id,
    fetch_recent_transactions,
    fetch_transaction_by_id,
    group_transactions as group_transactions_service,
    split_transaction as split_transaction_service,
    ungroup_transactions as ungroup_transactions_service,
    unsplit_transaction as unsplit_transaction_service,
    update_transaction as update_transaction_service,
    upload_transaction_attachment as upload_transaction_attachment_service,
)

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyApp, LunchMoneyDatabase


@mcp.tool()
async def get_recent_transactions(
    days: int = 30,
    limit: int = 50,
) -> list[TransactionInfo]:
    """Fetch recent transactions from the local database."""
    db: LunchMoneyDatabase = get_database()
    return await fetch_recent_transactions(db=db, days=days, limit=limit)


@mcp.tool()
async def get_transaction(transaction_id: int) -> TransactionInfo | None:
    """Fetch one synchronized transaction from the local database."""
    db: LunchMoneyDatabase = get_database()
    return await fetch_transaction_by_id(db=db, transaction_id=transaction_id)


@mcp.tool()
async def create_transactions(
    request: CreateNewTransactionsRequest,
) -> list[TransactionInfo]:
    """Create transactions upstream and cache their canonical responses."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await create_transactions_service(client=client, db=db, request=request)


@mcp.tool()
async def bulk_update_transactions(
    request: UpdateTransactionsRequest,
) -> list[TransactionInfo]:
    """Apply an upstream bulk transaction update and refresh local records."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await bulk_update_transactions_service(client=client, db=db, request=request)


@mcp.tool()
async def bulk_delete_transactions(request: DeleteTransactionsRequest) -> None:
    """Delete multiple transactions upstream and remove their cached records."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    await bulk_delete_transactions_service(client=client, db=db, request=request)


@mcp.tool()
async def update_transaction(
    transaction_id: int,
    request: UpdateTransactionObject,
    update_balance: bool | None = None,
) -> TransactionInfo:
    """Update one transaction upstream and cache Lunch Money's response."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await update_transaction_service(
        client=client,
        db=db,
        transaction_id=transaction_id,
        request=request,
        update_balance=update_balance,
    )


@mcp.tool()
async def delete_transaction(transaction_id: int) -> None:
    """Delete one transaction upstream and remove its cached record."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    await delete_transaction_service(
        client=client, db=db, transaction_id=transaction_id
    )


@mcp.tool()
async def group_transactions(request: GroupTransactionsRequest) -> TransactionInfo:
    """Create a transaction group upstream and cache its returned graph."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await group_transactions_service(client=client, db=db, request=request)


@mcp.tool()
async def ungroup_transactions(transaction_id: int) -> None:
    """Ungroup transactions upstream and refresh restored cached children."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    await ungroup_transactions_service(
        client=client,
        db=db,
        transaction_id=transaction_id,
    )


@mcp.tool()
async def split_transaction(
    transaction_id: int,
    request: SplitTransactionRequest,
) -> TransactionInfo:
    """Split a transaction upstream and cache the returned parent graph."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await split_transaction_service(
        client=client,
        db=db,
        transaction_id=transaction_id,
        request=request,
    )


@mcp.tool()
async def unsplit_transaction(transaction_id: int) -> None:
    """Unsplit a transaction upstream and replace its cached graph."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    await unsplit_transaction_service(
        client=client,
        db=db,
        transaction_id=transaction_id,
    )


@mcp.tool()
async def upload_attachment(
    transaction_id: int,
    request: TransactionAttachmentUploadRequest,
) -> TransactionAttachmentObject:
    """Upload a file upstream and reconcile cached attachment metadata."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await upload_transaction_attachment_service(
        client=client,
        db=db,
        transaction_id=transaction_id,
        file=request.to_api_file(),
        notes=request.notes,
    )


@mcp.tool()
async def get_attachment(file_id: int) -> GetTransactionAttachmentUrl200Response:
    """Return Lunch Money's signed URL for one transaction attachment."""
    client: LunchMoneyApp = get_lunchmoney_app()
    return await fetch_attachment_by_id(client=client, file_id=file_id)


@mcp.tool()
async def delete_attachment(file_id: int) -> None:
    """Delete an attachment upstream and reconcile its cached owner."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    await delete_transaction_attachment_service(client=client, db=db, file_id=file_id)


__all__ = [
    "bulk_delete_transactions",
    "bulk_update_transactions",
    "create_transactions",
    "delete_attachment",
    "delete_transaction",
    "get_attachment",
    "get_recent_transactions",
    "get_transaction",
    "group_transactions",
    "split_transaction",
    "ungroup_transactions",
    "unsplit_transaction",
    "update_transaction",
    "upload_attachment",
]
