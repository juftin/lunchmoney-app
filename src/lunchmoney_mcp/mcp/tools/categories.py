"""FastMCP tools for budget category operations."""

from typing import TYPE_CHECKING

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import CategoryInfo
from lunchmoney_mcp.services import fetch_categories, fetch_category_by_id

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyDatabase


@mcp.tool()
async def list_categories() -> list[CategoryInfo]:
    """List all budget categories and subcategories.

    Returns
    -------
    list[CategoryInfo]
        List of all budget category objects in database.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_categories(db=db)


@mcp.tool()
async def get_category(category_id: int) -> CategoryInfo | None:
    """Fetch one synchronized budget category.

    Parameters
    ----------
    category_id : int
        Identifier of the category to retrieve.

    Returns
    -------
    CategoryInfo | None
        Matching category, or ``None`` when it has not been synchronized.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_category_by_id(db=db, category_id=category_id)


__all__ = ["get_category", "list_categories"]
