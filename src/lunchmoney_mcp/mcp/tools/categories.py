"""FastMCP tools for budget category operations."""

from typing import TYPE_CHECKING

from lunchmoney.models import CreateCategoryRequestObject, UpdateCategoryRequestObject

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import CategoryInfo
from lunchmoney_mcp.services import (
    create_category as create_category_service,
    delete_category as delete_category_service,
    fetch_categories,
    fetch_category_by_id,
    update_category as update_category_service,
)

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyDatabase, LunchMoneyApp


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


@mcp.tool()
async def create_category(request: CreateCategoryRequestObject) -> CategoryInfo:
    """Create a budget category and cache Lunch Money's canonical response."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await create_category_service(client=client, db=db, request=request)


@mcp.tool()
async def update_category(
    category_id: int,
    request: UpdateCategoryRequestObject,
) -> CategoryInfo:
    """Update a budget category and cache Lunch Money's canonical response."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await update_category_service(
        client=client,
        db=db,
        category_id=category_id,
        request=request,
    )


@mcp.tool()
async def delete_category(
    category_id: int,
    force: bool | None = None,
) -> None:
    """Delete a budget category upstream and remove its cached row."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    await delete_category_service(
        client=client,
        db=db,
        category_id=category_id,
        force=force,
    )


__all__ = [
    "create_category",
    "delete_category",
    "get_category",
    "list_categories",
    "update_category",
]
