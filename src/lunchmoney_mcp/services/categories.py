"""Service logic for Categories data operations."""

from lunchmoney.models import (
    CategoryObject,
    CreateCategoryRequestObject,
    UpdateCategoryRequestObject,
)

from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Category, Transaction
from lunchmoney_mcp.schemas import CategoryInfo


def _category_info(category: Category) -> CategoryInfo:
    """Convert one persisted category into the public response schema."""
    return CategoryInfo(
        id=category.id,
        name=category.name,
        is_income=category.is_income,
        exclude_from_budget=category.exclude_from_budget,
        exclude_from_totals=category.exclude_from_totals,
        is_group=category.is_group,
        group_id=category.group_id,
    )


async def fetch_categories(db: LunchMoneyDatabase) -> list[CategoryInfo]:
    """Fetch all budget categories and subcategories from database.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    list[CategoryInfo]
        List of all budget category objects in database.
    """
    categories = await db.list(Category)
    return [_category_info(category) for category in categories]


async def fetch_category_by_id(
    db: LunchMoneyDatabase,
    category_id: int,
) -> CategoryInfo | None:
    """Fetch one synchronized budget category by identifier.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    category_id : int
        Identifier of the category to retrieve.

    Returns
    -------
    CategoryInfo | None
        Matching category, or ``None`` when it has not been synchronized.
    """
    category = await db.get(Category, category_id)
    if category is None:
        return None
    return _category_info(category)


async def _store_category(
    db: LunchMoneyDatabase,
    category: CategoryObject,
) -> CategoryInfo:
    """Persist an upstream category response and expose its public fields."""
    stored = await db.upsert(Category.from_api(category))
    return _category_info(stored)


async def create_category(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    request: CreateCategoryRequestObject,
) -> CategoryInfo:
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
    CategoryInfo
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
) -> CategoryInfo:
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
    CategoryInfo
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
