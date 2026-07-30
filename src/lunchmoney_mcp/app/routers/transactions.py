"""FastAPI endpoints for transaction queries and mutations."""

from typing import Annotated

from fastapi import APIRouter, Depends
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
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import TransactionAttachmentUploadRequest, TransactionInfo
from lunchmoney_mcp.services import (
    bulk_delete_transactions,
    bulk_update_transactions,
    create_transactions,
    delete_transaction,
    delete_transaction_attachment,
    fetch_attachment_by_id,
    fetch_recent_transactions,
    fetch_transaction_by_id,
    group_transactions,
    split_transaction,
    ungroup_transactions,
    unsplit_transaction,
    update_transaction,
    upload_transaction_attachment,
)

router = APIRouter(tags=["Transactions"])
"""FastAPI APIRouter for financial transaction endpoints."""


@router.get(
    path="/transactions",
    response_model=list[TransactionInfo],
    operation_id="get_recent_transactions",
)
async def get_recent_transactions(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    days: int = 30,
    limit: int = 50,
) -> list[TransactionInfo]:
    """Fetch recent transactions from the local database."""
    return await fetch_recent_transactions(db=db, days=days, limit=limit)


@router.post(
    path="/transactions",
    response_model=list[TransactionInfo],
    operation_id="create_transactions",
)
async def create_transactions_route(
    request: CreateNewTransactionsRequest,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> list[TransactionInfo]:
    """Create transactions upstream and cache their canonical responses."""
    return await create_transactions(client=client, db=db, request=request)


@router.put(
    path="/transactions",
    response_model=list[TransactionInfo],
    operation_id="bulk_update_transactions",
)
async def bulk_update_transactions_route(
    request: UpdateTransactionsRequest,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> list[TransactionInfo]:
    """Apply an upstream bulk transaction update and refresh local records."""
    return await bulk_update_transactions(client=client, db=db, request=request)


@router.delete(
    path="/transactions",
    status_code=204,
    operation_id="bulk_delete_transactions",
)
async def bulk_delete_transactions_route(
    request: DeleteTransactionsRequest,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> None:
    """Delete multiple transactions upstream and remove their cached records."""
    await bulk_delete_transactions(client=client, db=db, request=request)


@router.post(
    path="/transactions/group",
    response_model=TransactionInfo,
    operation_id="group_transactions",
)
async def group_transactions_route(
    request: GroupTransactionsRequest,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> TransactionInfo:
    """Create a transaction group upstream and cache its returned graph."""
    return await group_transactions(client=client, db=db, request=request)


@router.delete(
    path="/transactions/group/{transaction_id}",
    status_code=204,
    operation_id="ungroup_transactions",
)
async def ungroup_transactions_route(
    transaction_id: int,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> None:
    """Ungroup transactions upstream and refresh restored cached children."""
    await ungroup_transactions(client=client, db=db, transaction_id=transaction_id)


@router.post(
    path="/transactions/split/{transaction_id}",
    response_model=TransactionInfo,
    operation_id="split_transaction",
)
async def split_transaction_route(
    transaction_id: int,
    request: SplitTransactionRequest,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> TransactionInfo:
    """Split a transaction upstream and cache the returned parent graph."""
    return await split_transaction(
        client=client,
        db=db,
        transaction_id=transaction_id,
        request=request,
    )


@router.delete(
    path="/transactions/split/{transaction_id}",
    status_code=204,
    operation_id="unsplit_transaction",
)
async def unsplit_transaction_route(
    transaction_id: int,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> None:
    """Unsplit a transaction upstream and replace its cached graph."""
    await unsplit_transaction(client=client, db=db, transaction_id=transaction_id)


@router.post(
    path="/transactions/{transaction_id}/attachments",
    response_model=TransactionAttachmentObject,
    operation_id="upload_attachment",
)
async def upload_attachment(
    transaction_id: int,
    request: TransactionAttachmentUploadRequest,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> TransactionAttachmentObject:
    """Upload a transaction attachment upstream and reconcile cached metadata."""
    return await upload_transaction_attachment(
        client=client,
        db=db,
        transaction_id=transaction_id,
        file=request.to_api_file(),
        notes=request.notes,
    )


@router.get(
    path="/transactions/attachments/{file_id}",
    response_model=GetTransactionAttachmentUrl200Response,
    operation_id="get_attachment",
)
async def get_attachment(
    file_id: int,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
) -> GetTransactionAttachmentUrl200Response:
    """Return Lunch Money's signed URL for one transaction attachment."""
    return await fetch_attachment_by_id(client=client, file_id=file_id)


@router.delete(
    path="/transactions/attachments/{file_id}",
    status_code=204,
    operation_id="delete_attachment",
)
async def delete_attachment(
    file_id: int,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> None:
    """Delete one transaction attachment upstream and reconcile its cache."""
    await delete_transaction_attachment(client=client, db=db, file_id=file_id)


@router.get(
    path="/transactions/{transaction_id}",
    response_model=TransactionInfo | None,
    operation_id="get_transaction",
)
async def get_transaction(
    transaction_id: int,
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> TransactionInfo | None:
    """Fetch one synchronized transaction from the local database."""
    return await fetch_transaction_by_id(db=db, transaction_id=transaction_id)


@router.put(
    path="/transactions/{transaction_id}",
    response_model=TransactionInfo,
    operation_id="update_transaction",
)
async def update_transaction_route(
    transaction_id: int,
    request: UpdateTransactionObject,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    update_balance: bool | None = None,
) -> TransactionInfo:
    """Update one transaction upstream and cache Lunch Money's response."""
    return await update_transaction(
        client=client,
        db=db,
        transaction_id=transaction_id,
        request=request,
        update_balance=update_balance,
    )


@router.delete(
    path="/transactions/{transaction_id}",
    status_code=204,
    operation_id="delete_transaction",
)
async def delete_transaction_route(
    transaction_id: int,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> None:
    """Delete one transaction upstream and remove its cached record."""
    await delete_transaction(client=client, db=db, transaction_id=transaction_id)
