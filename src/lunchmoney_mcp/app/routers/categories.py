"""Categories data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Category
from lunchmoney_mcp.schemas import CategoryInfo

router = APIRouter(tags=["Categories"])


@router.get(path="/categories", response_model=list[CategoryInfo])
async def list_categories(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> list[CategoryInfo]:
    """List all budget categories and subcategories."""
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
