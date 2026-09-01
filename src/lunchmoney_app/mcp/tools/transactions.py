"""FastMCP transaction tools."""

from lunchmoney.models import (
    ChildTransactionObject,
    CreateNewTransactionsRequest,
    DeleteTransactionsRequest,
    GetTransactionAttachmentUrl200Response,
    GroupTransactionsRequest,
    SplitTransactionRequest,
    TransactionAttachmentObject,
    TransactionObject,
    UpdateTransactionObject,
    UpdateTransactionsRequest,
)

from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.schemas import (
    ReviewTransactionsQuery,
    ReviewTransactionsResponse,
    TransactionAttachmentUploadRequest,
    TransactionQuery,
)
from lunchmoney_app.services import (
    bulk_delete_transactions as bulk_delete_service,
    bulk_update_transactions as bulk_update_service,
    create_transactions as create_service,
    delete_transaction as delete_service,
    delete_transaction_attachment as delete_attachment_service,
    fetch_attachment_by_id,
    fetch_transactions,
    fetch_transaction_by_id,
    group_transactions as group_service,
    split_transaction as split_service,
    review_transactions as review_transactions_service,
    ungroup_transactions as ungroup_service,
    unsplit_transaction as unsplit_service,
    update_transaction as update_service,
    upload_transaction_attachment as upload_service,
)
from lunchmoney_app.services.operations import get_operation_context


@mcp.tool()
async def list_transactions(
    query: TransactionQuery | None = None,
) -> list[TransactionObject]:
    """List filtered transactions."""
    return await fetch_transactions(
        get_operation_context(), query or TransactionQuery()
    )


@mcp.tool()
async def review_transactions(
    query: ReviewTransactionsQuery | None = None,
) -> ReviewTransactionsResponse:
    """Return unreviewed transactions, their metadata, categories, and accounts."""
    return await review_transactions_service(
        get_operation_context(), query or ReviewTransactionsQuery()
    )


@mcp.tool()
async def get_transaction(
    transaction_id: int,
) -> TransactionObject | ChildTransactionObject | None:
    """Return one transaction graph when available."""
    return await fetch_transaction_by_id(get_operation_context(), transaction_id)


@mcp.tool()
async def create_transactions(
    request: CreateNewTransactionsRequest,
) -> list[TransactionObject]:
    """Create transactions upstream."""
    return await create_service(get_operation_context(), request)


@mcp.tool()
async def bulk_update_transactions(
    request: UpdateTransactionsRequest,
) -> list[TransactionObject]:
    """Bulk-update transactions upstream."""
    return await bulk_update_service(get_operation_context(), request)


@mcp.tool()
async def bulk_delete_transactions(request: DeleteTransactionsRequest) -> None:
    """Bulk-delete transactions upstream."""
    await bulk_delete_service(get_operation_context(), request)


@mcp.tool()
async def update_transaction(
    transaction_id: int,
    request: UpdateTransactionObject,
    update_balance: bool | None = None,
) -> TransactionObject:
    """Update one transaction upstream."""
    return await update_service(
        get_operation_context(), transaction_id, request, update_balance
    )


@mcp.tool()
async def delete_transaction(transaction_id: int) -> None:
    """Delete one transaction upstream."""
    await delete_service(get_operation_context(), transaction_id)


@mcp.tool()
async def group_transactions(request: GroupTransactionsRequest) -> TransactionObject:
    """Create a transaction group."""
    return await group_service(get_operation_context(), request)


@mcp.tool()
async def ungroup_transactions(transaction_id: int) -> None:
    """Ungroup a transaction group."""
    await ungroup_service(get_operation_context(), transaction_id)


@mcp.tool()
async def split_transaction(
    transaction_id: int, request: SplitTransactionRequest
) -> TransactionObject:
    """Split a transaction."""
    return await split_service(get_operation_context(), transaction_id, request)


@mcp.tool()
async def unsplit_transaction(transaction_id: int) -> None:
    """Unsplit a transaction."""
    await unsplit_service(get_operation_context(), transaction_id)


@mcp.tool()
async def upload_attachment(
    transaction_id: int,
    request: TransactionAttachmentUploadRequest,
) -> TransactionAttachmentObject:
    """Upload a transaction attachment."""
    return await upload_service(
        get_operation_context(), transaction_id, request.to_api_file(), request.notes
    )


@mcp.tool()
async def get_attachment(file_id: int) -> GetTransactionAttachmentUrl200Response:
    """Return a short-lived attachment URL."""
    return await fetch_attachment_by_id(get_operation_context(), file_id)


@mcp.tool()
async def delete_attachment(file_id: int) -> None:
    """Delete a transaction attachment."""
    await delete_attachment_service(get_operation_context(), file_id)


__all__ = [
    "bulk_delete_transactions",
    "bulk_update_transactions",
    "create_transactions",
    "delete_attachment",
    "delete_transaction",
    "get_attachment",
    "get_transaction",
    "group_transactions",
    "list_transactions",
    "review_transactions",
    "split_transaction",
    "ungroup_transactions",
    "unsplit_transaction",
    "update_transaction",
    "upload_attachment",
]
