"""Service logic for Categories data operations."""

from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Category
from lunchmoney_mcp.schemas import CategoryInfo


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
    return [
        CategoryInfo(
            id=c.id,
            name=c.name,
            is_income=c.is_income,
            exclude_from_budget=c.exclude_from_budget,
            exclude_from_totals=c.exclude_from_totals,
            is_group=c.is_group,
            group_id=c.group_id,
        )
        for c in categories
    ]


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
    return CategoryInfo(
        id=category.id,
        name=category.name,
        is_income=category.is_income,
        exclude_from_budget=category.exclude_from_budget,
        exclude_from_totals=category.exclude_from_totals,
        is_group=category.is_group,
        group_id=category.group_id,
    )
