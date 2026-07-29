"""FastMCP tools for budget category operations."""

from typing import TYPE_CHECKING

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import CategoryInfo
from lunchmoney_mcp.services import fetch_categories

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


__all__ = ["list_categories"]
