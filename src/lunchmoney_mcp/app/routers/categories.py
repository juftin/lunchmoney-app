"""Categories data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import CategoryInfo
from lunchmoney_mcp.services import fetch_categories

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
