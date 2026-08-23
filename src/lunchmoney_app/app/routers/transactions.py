"""Transaction query and mutation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
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

from lunchmoney_app.app.dependencies import OperationContext, get_operation_context
from lunchmoney_app.schemas import TransactionAttachmentUploadRequest, TransactionQuery
from lunchmoney_app.services import (
    bulk_delete_transactions,
    bulk_update_transactions,
    create_transactions,
    delete_transaction,
    delete_transaction_attachment,
    fetch_attachment_by_id,
    fetch_transactions,
    fetch_transaction_by_id,
    group_transactions,
    split_transaction,
    ungroup_transactions,
    unsplit_transaction,
    update_transaction,
    upload_transaction_attachment,
)

router = APIRouter(tags=["Transactions"])
ContextDep = Annotated[OperationContext, Depends(dependency=get_operation_context)]


@router.get(
    path="/transactions",
    response_model=list[TransactionObject],
    operation_id="list_transactions",
)
async def list_transactions(
    context: ContextDep, query: Annotated[TransactionQuery, Depends()]
) -> list[TransactionObject]:
    """List filtered transactions."""
    return await fetch_transactions(context, query)


@router.post(
    path="/transactions",
    response_model=list[TransactionObject],
    operation_id="create_transactions",
)
async def create_transactions_route(
    request: CreateNewTransactionsRequest, context: ContextDep
) -> list[TransactionObject]:
    """Create transactions upstream."""
    return await create_transactions(context, request)


@router.put(
    path="/transactions",
    response_model=list[TransactionObject],
    operation_id="bulk_update_transactions",
)
async def bulk_update_transactions_route(
    request: UpdateTransactionsRequest, context: ContextDep
) -> list[TransactionObject]:
    """Bulk-update transactions upstream."""
    return await bulk_update_transactions(context, request)


@router.delete(
    path="/transactions", status_code=204, operation_id="bulk_delete_transactions"
)
async def bulk_delete_transactions_route(
    request: DeleteTransactionsRequest, context: ContextDep
) -> None:
    """Bulk-delete transactions upstream."""
    await bulk_delete_transactions(context, request)


@router.post(
    path="/transactions/group",
    response_model=TransactionObject,
    operation_id="group_transactions",
)
async def group_transactions_route(
    request: GroupTransactionsRequest, context: ContextDep
) -> TransactionObject:
    """Create a transaction group."""
    return await group_transactions(context, request)


@router.delete(
    path="/transactions/group/{transaction_id}",
    status_code=204,
    operation_id="ungroup_transactions",
)
async def ungroup_transactions_route(transaction_id: int, context: ContextDep) -> None:
    """Ungroup a transaction group."""
    await ungroup_transactions(context, transaction_id)


@router.post(
    path="/transactions/split/{transaction_id}",
    response_model=TransactionObject,
    operation_id="split_transaction",
)
async def split_transaction_route(
    transaction_id: int, request: SplitTransactionRequest, context: ContextDep
) -> TransactionObject:
    """Split a transaction."""
    return await split_transaction(context, transaction_id, request)


@router.delete(
    path="/transactions/split/{transaction_id}",
    status_code=204,
    operation_id="unsplit_transaction",
)
async def unsplit_transaction_route(transaction_id: int, context: ContextDep) -> None:
    """Unsplit a transaction."""
    await unsplit_transaction(context, transaction_id)


@router.post(
    path="/transactions/{transaction_id}/attachments",
    response_model=TransactionAttachmentObject,
    operation_id="upload_attachment",
)
async def upload_attachment(
    transaction_id: int,
    request: TransactionAttachmentUploadRequest,
    context: ContextDep,
) -> TransactionAttachmentObject:
    """Upload a transaction attachment."""
    return await upload_transaction_attachment(
        context, transaction_id, request.to_api_file(), request.notes
    )


@router.get(
    path="/transactions/attachments/{file_id}",
    response_model=GetTransactionAttachmentUrl200Response,
    operation_id="get_attachment",
)
async def get_attachment(
    file_id: int, context: ContextDep
) -> GetTransactionAttachmentUrl200Response:
    """Return a short-lived attachment URL."""
    return await fetch_attachment_by_id(context, file_id)


@router.delete(
    path="/transactions/attachments/{file_id}",
    status_code=204,
    operation_id="delete_attachment",
)
async def delete_attachment(file_id: int, context: ContextDep) -> None:
    """Delete a transaction attachment."""
    await delete_transaction_attachment(context, file_id)


@router.get(
    path="/transactions/{transaction_id}",
    response_model=TransactionObject | ChildTransactionObject | None,
    operation_id="get_transaction",
)
async def get_transaction(
    transaction_id: int, context: ContextDep
) -> TransactionObject | ChildTransactionObject | None:
    """Return one transaction graph when available."""
    return await fetch_transaction_by_id(context, transaction_id)


@router.put(
    path="/transactions/{transaction_id}",
    response_model=TransactionObject,
    operation_id="update_transaction",
)
async def update_transaction_route(
    transaction_id: int,
    request: UpdateTransactionObject,
    context: ContextDep,
    update_balance: bool | None = None,
) -> TransactionObject:
    """Update one transaction."""
    return await update_transaction(context, transaction_id, request, update_balance)


@router.delete(
    path="/transactions/{transaction_id}",
    status_code=204,
    operation_id="delete_transaction",
)
async def delete_transaction_route(transaction_id: int, context: ContextDep) -> None:
    """Delete one transaction."""
    await delete_transaction(context, transaction_id)
