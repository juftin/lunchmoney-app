"""Regression tests for Sprint 3 transaction mutations and attachments."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, create_autospec

import pytest
from lunchmoney.models import (
    CreateNewTransactionsRequest,
    DeleteTransactionsRequest,
    GroupTransactionsRequest,
    SplitTransactionRequest,
    UpdateTransactionObject,
    UpdateTransactionsRequest,
)

from database.factories import transaction_attachment_object, transaction_object
from lunchmoney_app.app.main import fastapi_app
from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import Transaction
from lunchmoney_app.mcp import mcp
from lunchmoney_app.services import (
    bulk_delete_transactions,
    bulk_update_transactions,
    create_transactions,
    delete_transaction,
    delete_transaction_attachment,
    fetch_attachment_by_id,
    group_transactions,
    split_transaction,
    ungroup_transactions,
    unsplit_transaction,
    update_transaction,
    upload_transaction_attachment,
)
from lunchmoney_app.services.operations import StatefulOperationContextFactory


def _create_request() -> CreateNewTransactionsRequest:
    """Build a minimal valid transaction-insert request."""
    return CreateNewTransactionsRequest.model_validate(
        {
            "transactions": [
                {"date": "2026-01-01", "amount": {"actual_instance": "12.5000"}}
            ]
        }
    )


def _bulk_update_request() -> UpdateTransactionsRequest:
    """Build a minimal valid bulk transaction-update request."""
    return UpdateTransactionsRequest.model_validate(
        {"transactions": [{"id": 100, "payee": "Updated payee"}]}
    )


def _group_request() -> GroupTransactionsRequest:
    """Build a minimal valid transaction-group request."""
    return GroupTransactionsRequest.model_validate(
        {"ids": [100, 101], "date": "2026-01-01", "payee": "Grouped payee"}
    )


def _split_request() -> SplitTransactionRequest:
    """Build a minimal valid transaction-split request."""
    return SplitTransactionRequest.model_validate(
        {
            "child_transactions": [
                {"amount": {"actual_instance": "6.2500"}},
                {"amount": {"actual_instance": "6.2500"}},
            ]
        }
    )


@pytest.mark.asyncio
async def test_transaction_writes_cache_canonical_upstream_responses() -> None:
    """Persist every response-bearing mutation only after its upstream call."""
    transaction = transaction_object(tag_ids=[])
    create = AsyncMock(return_value=SimpleNamespace(transactions=[transaction]))
    bulk_update = AsyncMock(return_value=SimpleNamespace(transactions=[transaction]))
    update = AsyncMock(return_value=transaction)
    group = AsyncMock(return_value=transaction)
    split = AsyncMock(return_value=transaction)
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                transactions_bulk=SimpleNamespace(
                    create_new_transactions=create,
                    update_transactions=bulk_update,
                ),
                transactions=SimpleNamespace(update_transaction=update),
                transactions_group=SimpleNamespace(group_transactions=group),
                transactions_split=SimpleNamespace(split_transaction=split),
            )
        ),
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.list = AsyncMock(return_value=[])
    database.upsert = AsyncMock(side_effect=lambda record: record)
    create_request = _create_request()
    bulk_request = _bulk_update_request()
    update_request = UpdateTransactionObject(payee="Updated payee")
    group_request = _group_request()
    split_request = _split_request()

    async with StatefulOperationContextFactory(client, database).operation() as context:
        created = await create_transactions(context, create_request)
        updated = await bulk_update_transactions(context, bulk_request)
        selected = await update_transaction(
            context, transaction.id, update_request, update_balance=False
        )
        grouped = await group_transactions(context, group_request)
        split_result = await split_transaction(context, transaction.id, split_request)

    assert [item.id for item in created] == [transaction.id]
    assert [item.id for item in updated] == [transaction.id]
    assert selected.id == transaction.id
    assert grouped.id == transaction.id
    assert split_result.id == transaction.id
    create.assert_awaited_once_with(create_new_transactions_request=create_request)
    bulk_update.assert_awaited_once_with(update_transactions_request=bulk_request)
    update.assert_awaited_once_with(
        id=transaction.id,
        update_transaction_object=update_request,
        update_balance=False,
    )
    group.assert_awaited_once_with(group_transactions_request=group_request)
    split.assert_awaited_once_with(
        id=transaction.id,
        split_transaction_request=split_request,
    )
    assert database.upsert.await_count == 5
    assert database.delete_cached_responses.await_count == 10
    database.delete_cached_responses.assert_any_await("summary:")
    database.delete_cached_responses.assert_any_await("health:stale:transactions")


@pytest.mark.asyncio
async def test_transaction_deletes_reconcile_cached_records_after_upstream_success() -> (
    None
):
    """Remove deleted records only after the corresponding upstream mutation."""
    transaction = transaction_object(tag_ids=[])
    bulk_delete = AsyncMock()
    single_delete = AsyncMock()
    ungroup = AsyncMock()
    unsplit = AsyncMock()
    get_transaction = AsyncMock(return_value=transaction)
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                transactions_bulk=SimpleNamespace(delete_transactions=bulk_delete),
                transactions=SimpleNamespace(
                    delete_transaction_by_id=single_delete,
                    get_transaction_by_id=get_transaction,
                ),
                transactions_group=SimpleNamespace(ungroup_transactions=ungroup),
                transactions_split=SimpleNamespace(unsplit_transaction=unsplit),
            )
        ),
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.get = AsyncMock(return_value=None)
    database.list = AsyncMock(return_value=[])
    database.delete = AsyncMock(return_value=True)
    database.upsert = AsyncMock(side_effect=lambda record: record)
    bulk_request = DeleteTransactionsRequest(ids=[100, 101])

    async with StatefulOperationContextFactory(client, database).operation() as context:
        await bulk_delete_transactions(context, bulk_request)
        await delete_transaction(context, transaction.id)
        await ungroup_transactions(context, transaction.id)
        await unsplit_transaction(context, transaction.id)

    bulk_delete.assert_awaited_once_with(delete_transactions_request=bulk_request)
    single_delete.assert_awaited_once_with(id=transaction.id)
    ungroup.assert_awaited_once_with(id=transaction.id)
    unsplit.assert_awaited_once_with(id=transaction.id)
    get_transaction.assert_awaited_once_with(id=transaction.id)
    database.delete.assert_any_await(Transaction, 100)
    database.delete.assert_any_await(Transaction, 101)
    database.delete.assert_any_await(Transaction, transaction.id)
    database.upsert.assert_awaited_once()
    assert database.delete_cached_responses.await_count == 8
    database.delete_cached_responses.assert_any_await("summary:")
    database.delete_cached_responses.assert_any_await("health:stale:transactions")


@pytest.mark.asyncio
async def test_attachment_operations_reconcile_known_cached_transaction() -> None:
    """Cache upload metadata and remove it after a successful upstream delete."""
    transaction = Transaction.from_api(transaction_object(tag_ids=[]))
    attachment = transaction_attachment_object()
    attach = AsyncMock(return_value=attachment)
    get_url = AsyncMock(
        return_value=SimpleNamespace(url="https://example.invalid/file")
    )
    delete = AsyncMock()
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                transactions_files=SimpleNamespace(
                    attach_file_to_transaction=attach,
                    get_transaction_attachment_url=get_url,
                    delete_transaction_attachment=delete,
                )
            )
        ),
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.get = AsyncMock(return_value=transaction)
    database.upsert = AsyncMock(side_effect=lambda record: record)
    database.delete_transaction_attachment = AsyncMock(return_value=True)

    async with StatefulOperationContextFactory(client, database).operation() as context:
        uploaded = await upload_transaction_attachment(
            context,
            transaction.id,
            ("receipt.pdf", b"synthetic"),
            notes="Receipt",
        )
        url = await fetch_attachment_by_id(context, attachment.id or 0)
        await delete_transaction_attachment(context, attachment.id or 0)

    assert uploaded == attachment
    assert url.url == "https://example.invalid/file"
    attach.assert_awaited_once_with(
        transaction_id=transaction.id,
        file=("receipt.pdf", b"synthetic"),
        notes="Receipt",
    )
    get_url.assert_awaited_once_with(file_id=attachment.id)
    delete.assert_awaited_once_with(file_id=attachment.id)
    database.delete_transaction_attachment.assert_awaited_once_with(attachment.id)
    assert database.upsert.await_count == 1


def test_transaction_mutation_routes_are_registered() -> None:
    """Publish every Sprint 3 REST endpoint in the generated OpenAPI document."""
    paths = fastapi_app.openapi()["paths"]

    assert {"post", "put", "delete"} <= set(paths["/api/transactions"])
    assert {"get"} <= set(paths["/api/transactions/review"])
    assert {"put", "delete"} <= set(paths["/api/transactions/{transaction_id}"])
    assert {"post"} <= set(paths["/api/transactions/group"])
    assert {"delete"} <= set(paths["/api/transactions/group/{transaction_id}"])
    assert {"post", "delete"} <= set(paths["/api/transactions/split/{transaction_id}"])
    assert {"post"} <= set(paths["/api/transactions/{transaction_id}/attachments"])
    assert {"get", "delete"} <= set(paths["/api/transactions/attachments/{file_id}"])


@pytest.mark.asyncio
async def test_transaction_mutation_mcp_tools_are_registered() -> None:
    """Publish every Sprint 3 mutation tool on the shared FastMCP instance."""
    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert {
        "create_transactions",
        "bulk_update_transactions",
        "bulk_delete_transactions",
        "update_transaction",
        "delete_transaction",
        "group_transactions",
        "ungroup_transactions",
        "split_transaction",
        "unsplit_transaction",
        "upload_attachment",
        "get_attachment",
        "delete_attachment",
    } <= tool_names
