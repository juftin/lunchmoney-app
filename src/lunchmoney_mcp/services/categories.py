"""Service logic for Categories data operations."""

from lunchmoney.models import (
    CategoryObject,
    ChildCategoryObject,
    CreateCategoryRequestObject,
    UpdateCategoryRequestObject,
)

from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Category, CategoryKind, Transaction
from lunchmoney_mcp.schemas import CategoryQuery


async def fetch_categories(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    query: CategoryQuery,
    live: bool,
) -> list[CategoryObject]:
    """Return categories in the configured live or persisted representation.

    Parameters
    ----------
    client
        Configured Lunch Money API client for stateless requests.
    db : LunchMoneyDatabase
        Database manager instance.
    query
        Upstream-compatible category collection controls.
    live
        Whether the server should read the current upstream response.

    Returns
    -------
    list[CategoryObject]
        Category objects in the requested hierarchy representation.
    """
    if live:
        response = await client.client.categories.get_all_categories(
            **query.model_dump(exclude_none=True)
        )
        return response.categories or []

    categories = await db.list(Category)
    return _filter_persisted_categories(categories=categories, query=query)


def _category_sort_key(category: Category) -> tuple[bool, int, str]:
    """Order cached categories like Lunch Money's collection response."""
    return (
        category.order is None,
        category.order if category.order is not None else 0,
        category.name.casefold(),
    )


def _as_flat_category(category: Category) -> CategoryObject:
    """Convert a cached parent or child row into a flat upstream category object."""
    category_object = category.to_api()
    return CategoryObject.model_validate(
        {
            **category_object.model_dump(mode="python"),
            "children": None,
        }
    )


def _as_nested_category(category: Category) -> CategoryObject:
    """Convert a cached top-level row into an upstream category object."""
    return CategoryObject.model_validate(category.to_api().model_dump(mode="python"))


def _filter_persisted_categories(
    categories: list[Category],
    query: CategoryQuery,
) -> list[CategoryObject]:
    """Apply Lunch Money category collection controls to cached category records."""
    if query.is_group is True:
        matching = [
            category
            for category in categories
            if category.kind == CategoryKind.PARENT and category.is_group
        ]
        return [
            _as_nested_category(category)
            for category in sorted(matching, key=_category_sort_key)
        ]

    if query.is_group is False:
        matching = [
            category
            for category in categories
            if category.kind == CategoryKind.PARENT
            and not category.is_group
            and category.group_id is None
        ]
        return [
            _as_nested_category(category)
            for category in sorted(matching, key=_category_sort_key)
        ]

    if query.format == "flattened":
        return [
            _as_flat_category(category)
            for category in sorted(categories, key=_category_sort_key)
        ]

    matching = [
        category for category in categories if category.kind == CategoryKind.PARENT
    ]
    return [
        _as_nested_category(category)
        for category in sorted(matching, key=_category_sort_key)
    ]


async def fetch_category_by_id(
    db: LunchMoneyDatabase,
    category_id: int,
) -> CategoryObject | ChildCategoryObject | None:
    """Fetch one synchronized budget category by identifier.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    category_id : int
        Identifier of the category to retrieve.

    Returns
    -------
    CategoryObject | ChildCategoryObject | None
        Matching category, or ``None`` when it has not been synchronized.
    """
    category = await db.get(Category, category_id)
    if category is None:
        return None
    return category.to_api()


async def _store_category(
    db: LunchMoneyDatabase,
    category: CategoryObject,
) -> CategoryObject:
    """Persist an upstream category response and preserve all its fields."""
    await db.upsert(Category.from_api(category))
    return category


async def create_category(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    request: CreateCategoryRequestObject,
) -> CategoryObject:
    """Create a category upstream before saving its canonical response locally.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    db : LunchMoneyDatabase
        Database manager that stores the canonical response.
    request : CreateCategoryRequestObject
        Validated category fields accepted by Lunch Money.

    Returns
    -------
    CategoryObject
        Created category after its local cache has been updated.
    """
    category = await client.client.categories.create_category(
        create_category_request_object=request,
    )
    return await _store_category(db=db, category=category)


async def update_category(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    category_id: int,
    request: UpdateCategoryRequestObject,
) -> CategoryObject:
    """Update a category upstream before saving its canonical response locally.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    db : LunchMoneyDatabase
        Database manager that stores the canonical response.
    category_id : int
        Identifier of the category to update.
    request : UpdateCategoryRequestObject
        Validated fields to update.

    Returns
    -------
    CategoryObject
        Updated category after its local cache has been updated.
    """
    category = await client.client.categories.update_category(
        id=category_id,
        update_category_request_object=request,
    )
    return await _store_category(db=db, category=category)


async def delete_category(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    category_id: int,
    force: bool | None = None,
) -> None:
    """Delete a category upstream before removing it from the local cache.

    Parameters
    ----------
    client : LunchMoneyApp
        Configured Lunch Money API client.
    db : LunchMoneyDatabase
        Database manager that removes the stale cached row.
    category_id : int
        Identifier of the category to delete.
    force : bool | None
        Whether Lunch Money may delete a category with dependencies.
    """
    await client.client.categories.delete_category(id=category_id, force=force)
    transactions = await db.list(Transaction)
    affected_transactions = [
        transaction
        for transaction in transactions
        if transaction.category_id == category_id
    ]
    for transaction in affected_transactions:
        transaction.category_id = None
    if affected_transactions:
        await db.upsert_many(affected_transactions)
    await db.delete(Category, category_id)
