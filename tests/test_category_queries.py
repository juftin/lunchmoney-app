"""Tests for source-independent upstream-compatible category queries."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, create_autospec

import pytest
from lunchmoney.models import GetAllCategories200Response

from database.factories import category_object, child_category_object
from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import Category
from lunchmoney_app.schemas import CategoryQuery
from lunchmoney_app.services import fetch_categories


@pytest.mark.asyncio
async def test_live_category_query_forwards_upstream_controls() -> None:
    """Forward hierarchy and group controls when the server reads live data."""
    response = GetAllCategories200Response(categories=[category_object()])
    get_all_categories = AsyncMock(return_value=response)
    client = cast(
        LunchMoneyApp,
        SimpleNamespace(
            client=SimpleNamespace(
                categories=SimpleNamespace(get_all_categories=get_all_categories)
            )
        ),
    )

    result = await fetch_categories(
        client=client,
        db=create_autospec(LunchMoneyDatabase, instance=True),
        query=CategoryQuery(format="flattened", is_group=False),
        live=True,
    )

    assert result == [category_object()]
    get_all_categories.assert_awaited_once_with(format="flattened", is_group=False)


@pytest.mark.asyncio
async def test_persisted_category_query_recreates_upstream_views() -> None:
    """Render nested, flattened, and group-filtered views from cached records."""
    group = Category.from_api(category_object(children=[child_category_object()]))
    standalone = Category.from_api(category_object())
    standalone.id = 12
    standalone.name = "Standalone category"
    database = create_autospec(LunchMoneyDatabase, instance=True)
    database.list = AsyncMock(return_value=[group, *group.children, standalone])
    client = create_autospec(LunchMoneyApp, instance=True)

    nested = await fetch_categories(
        client=client,
        db=database,
        query=CategoryQuery(format="nested"),
        live=False,
    )
    flattened = await fetch_categories(
        client=client,
        db=database,
        query=CategoryQuery(format="flattened"),
        live=False,
    )
    groups = await fetch_categories(
        client=client,
        db=database,
        query=CategoryQuery(is_group=True),
        live=False,
    )
    ungrouped = await fetch_categories(
        client=client,
        db=database,
        query=CategoryQuery(is_group=False),
        live=False,
    )

    assert [category.id for category in nested] == [standalone.id, group.id]
    nested_group = next(category for category in nested if category.id == group.id)
    assert nested_group.children is not None
    assert [child.id for child in nested_group.children] == [11]
    assert {category.id for category in flattened} == {10, 11, 12}
    assert all(category.children is None for category in flattened)
    assert [category.id for category in groups] == [group.id]
    assert [category.id for category in ungrouped] == [standalone.id]
