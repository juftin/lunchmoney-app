"""Regression tests for final Lunch Money tag mutations."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, create_autospec

import pytest
from lunchmoney.models import CreateTagRequestObject, UpdateTagRequestObject

from database.factories import tag_object, transaction_object
from lunchmoney_app.app.main import fastapi_app
from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import Tag, Transaction
from lunchmoney_app.mcp import mcp
from lunchmoney_app.services import create_tag, delete_tag, update_tag
from lunchmoney_app.services.operations import StatefulOperationContextFactory


@pytest.mark.asyncio
async def test_tag_mutations_write_upstream_before_cache_updates() -> None:
    """Persist canonical tag responses only after upstream writes succeed."""
    tag = tag_object()
    create = AsyncMock(return_value=tag)
    update = AsyncMock(return_value=tag)
    delete = AsyncMock()
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                tags=SimpleNamespace(
                    create_tag=create,
                    update_tag=update,
                    delete_tag=delete,
                )
            )
        ),
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.list = AsyncMock(return_value=[])
    database.upsert = AsyncMock(side_effect=lambda record: record)
    database.delete = AsyncMock(return_value=True)
    create_request = CreateTagRequestObject(name="Synthetic tag")
    update_request = UpdateTagRequestObject(name="Updated tag")

    async with StatefulOperationContextFactory(client, database).operation() as context:
        created = await create_tag(context, create_request)
        updated = await update_tag(context, tag.id, update_request)
        await delete_tag(context, tag.id, force=True)

    assert created.id == tag.id
    assert updated.name == tag.name
    create.assert_awaited_once_with(create_tag_request_object=create_request)
    update.assert_awaited_once_with(
        id=tag.id,
        update_tag_request_object=update_request,
    )
    delete.assert_awaited_once_with(id=tag.id, force=True)
    assert database.upsert.await_count == 2
    database.delete.assert_awaited_once_with(Tag, tag.id)


@pytest.mark.asyncio
async def test_tag_deletion_removes_cached_transaction_links() -> None:
    """Remove cached links before deleting a tag protected by foreign keys."""
    tag = Tag.from_api(tag_object())
    transaction = Transaction.from_api(transaction_object(tag_ids=[tag.id]))
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(tags=SimpleNamespace(delete_tag=AsyncMock()))
        ),
    )
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.list = AsyncMock(return_value=[transaction])
    database.upsert_many = AsyncMock()
    database.delete = AsyncMock(return_value=True)

    async with StatefulOperationContextFactory(client, database).operation() as context:
        await delete_tag(context, tag.id)

    assert transaction.tag_links == []
    database.upsert_many.assert_awaited_once_with([transaction])
    database.delete.assert_awaited_once_with(Tag, tag.id)


def test_tag_mutation_routes_are_registered() -> None:
    """Publish all tag mutation endpoints in the generated OpenAPI document."""
    paths = fastapi_app.openapi()["paths"]

    assert {"post"} <= set(paths["/api/tags"])
    assert {"put", "delete"} <= set(paths["/api/tags/{tag_id}"])


@pytest.mark.asyncio
async def test_tag_mutation_mcp_tools_are_registered() -> None:
    """Publish every tag mutation tool on the shared FastMCP instance."""
    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert {"create_tag", "update_tag", "delete_tag"} <= tool_names
