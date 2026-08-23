"""Service logic for transaction queries and upstream-first mutations."""

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

from lunchmoney_app.schemas import TransactionQuery
from lunchmoney_app.services.operations import OperationContext


async def fetch_transactions(
    context: OperationContext,
    query: TransactionQuery,
) -> list[TransactionObject]:
    """Return every matching transaction through the selected reader."""
    return await context.transactions.list(query)


async def fetch_transaction_by_id(
    context: OperationContext,
    transaction_id: int,
) -> TransactionObject | ChildTransactionObject | None:
    """Return one transaction graph when available."""
    return await context.transactions.get(transaction_id)


async def create_transactions(
    context: OperationContext,
    request: CreateNewTransactionsRequest,
) -> list[TransactionObject]:
    """Create transactions upstream, then apply mode-specific projection."""
    response = await context.client.client.transactions_bulk.create_new_transactions(
        create_new_transactions_request=request
    )
    transactions = list(response.transactions)
    await context.project("transactions", context.transactions.store_many(transactions))
    return transactions


async def bulk_update_transactions(
    context: OperationContext,
    request: UpdateTransactionsRequest,
) -> list[TransactionObject]:
    """Update transactions upstream, then apply mode-specific projection."""
    response = await context.client.client.transactions_bulk.update_transactions(
        update_transactions_request=request
    )
    transactions = list(response.transactions)
    await context.project("transactions", context.transactions.store_many(transactions))
    return transactions


async def bulk_delete_transactions(
    context: OperationContext,
    request: DeleteTransactionsRequest,
) -> None:
    """Delete transactions upstream, then apply mode-specific projection."""
    await context.client.client.transactions_bulk.delete_transactions(
        delete_transactions_request=request
    )
    await context.project(
        "transactions", context.transactions.delete_many(list(request.ids))
    )


async def update_transaction(
    context: OperationContext,
    transaction_id: int,
    request: UpdateTransactionObject,
    update_balance: bool | None = None,
) -> TransactionObject:
    """Update one transaction upstream, then project its canonical graph."""
    transaction = await context.client.client.transactions.update_transaction(
        id=transaction_id,
        update_transaction_object=request,
        update_balance=update_balance,
    )
    await context.project(
        "transactions", context.transactions.store_many([transaction])
    )
    return transaction


async def delete_transaction(
    context: OperationContext,
    transaction_id: int,
) -> None:
    """Delete one transaction upstream, then reconcile selected state."""
    await context.client.client.transactions.delete_transaction_by_id(id=transaction_id)
    await context.project(
        "transactions", context.transactions.delete_many([transaction_id])
    )


async def group_transactions(
    context: OperationContext,
    request: GroupTransactionsRequest,
) -> TransactionObject:
    """Create a transaction group upstream, then project its graph."""
    transaction = await context.client.client.transactions_group.group_transactions(
        group_transactions_request=request
    )
    await context.project(
        "transactions", context.transactions.store_many([transaction])
    )
    return transaction


async def ungroup_transactions(
    context: OperationContext,
    transaction_id: int,
) -> None:
    """Resolve group children, ungroup upstream, then reconcile selected state."""
    child_ids = await context.transactions.group_child_ids(transaction_id)
    await context.client.client.transactions_group.ungroup_transactions(
        id=transaction_id
    )
    restored = [
        await context.client.client.transactions.get_transaction_by_id(id=child_id)
        for child_id in child_ids
    ]
    await context.project(
        "transactions",
        context.transactions.replace_ungrouped(transaction_id, restored),
    )


async def split_transaction(
    context: OperationContext,
    transaction_id: int,
    request: SplitTransactionRequest,
) -> TransactionObject:
    """Split a transaction upstream, then project its canonical graph."""
    transaction = await context.client.client.transactions_split.split_transaction(
        id=transaction_id, split_transaction_request=request
    )
    await context.project(
        "transactions", context.transactions.store_many([transaction])
    )
    return transaction


async def unsplit_transaction(
    context: OperationContext,
    transaction_id: int,
) -> None:
    """Unsplit upstream, fetch the restored parent, then reconcile state."""
    await context.client.client.transactions_split.unsplit_transaction(
        id=transaction_id
    )
    restored = await context.client.client.transactions.get_transaction_by_id(
        id=transaction_id
    )
    await context.project(
        "transactions",
        context.transactions.replace_unsplit(transaction_id, restored),
    )


async def upload_transaction_attachment(
    context: OperationContext,
    transaction_id: int,
    file: bytes | tuple[str, bytes],
    notes: str | None = None,
) -> TransactionAttachmentObject:
    """Upload a file upstream, then project returned attachment metadata."""
    attachment = (
        await context.client.client.transactions_files.attach_file_to_transaction(
            transaction_id=transaction_id, file=file, notes=notes
        )
    )
    await context.project(
        "transactions",
        context.transactions.store_attachment(transaction_id, attachment),
    )
    return attachment


async def fetch_attachment_by_id(
    context: OperationContext,
    file_id: int,
) -> GetTransactionAttachmentUrl200Response:
    """Return Lunch Money's short-lived URL for one attachment."""
    return (
        await context.client.client.transactions_files.get_transaction_attachment_url(
            file_id=file_id
        )
    )


async def delete_transaction_attachment(
    context: OperationContext,
    file_id: int,
) -> None:
    """Delete an attachment upstream, then reconcile selected state."""
    await context.client.client.transactions_files.delete_transaction_attachment(
        file_id=file_id
    )
    await context.project(
        "transactions", context.transactions.delete_attachment(file_id)
    )
