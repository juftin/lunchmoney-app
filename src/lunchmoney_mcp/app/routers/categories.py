"""Categories data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import CategoryInfo
from lunchmoney_mcp.services import fetch_categories, fetch_category_by_id

router = APIRouter(tags=["Categories"])
"""FastAPI APIRouter for budget categories endpoints."""


@router.get(
    path="/categories",
    response_model=list[CategoryInfo],
    operation_id="list_categories",
)
async def list_categories(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> list[CategoryInfo]:
    """List all budget categories and subcategories.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    list[CategoryInfo]
        List of all budget category objects in database.
    """
    return await fetch_categories(db=db)


@router.get(
    path="/categories/{category_id}",
    response_model=CategoryInfo | None,
    operation_id="get_category",
)
async def get_category(
    category_id: int,
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> CategoryInfo | None:
    """Fetch one synchronized budget category.

    Parameters
    ----------
    category_id : int
        Identifier of the category to retrieve.
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    CategoryInfo | None
        Matching category, or ``None`` when it has not been synchronized.
    """
    return await fetch_category_by_id(db=db, category_id=category_id)
