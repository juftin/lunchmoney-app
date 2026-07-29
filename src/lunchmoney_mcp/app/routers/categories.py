"""Categories data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import CreateCategoryRequestObject, UpdateCategoryRequestObject

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import CategoryInfo
from lunchmoney_mcp.services import (
    create_category as create_category_service,
    delete_category as delete_category_service,
    fetch_categories,
    fetch_category_by_id,
    update_category as update_category_service,
)

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


@router.post(
    path="/categories",
    response_model=CategoryInfo,
    operation_id="create_category",
)
async def create_category(
    request: CreateCategoryRequestObject,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> CategoryInfo:
    """Create a budget category and store Lunch Money's canonical response."""
    return await create_category_service(client=client, db=db, request=request)


@router.put(
    path="/categories/{category_id}",
    response_model=CategoryInfo,
    operation_id="update_category",
)
async def update_category(
    category_id: int,
    request: UpdateCategoryRequestObject,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> CategoryInfo:
    """Update a budget category and store Lunch Money's canonical response."""
    return await update_category_service(
        client=client,
        db=db,
        category_id=category_id,
        request=request,
    )


@router.delete(
    path="/categories/{category_id}",
    status_code=204,
    operation_id="delete_category",
)
async def delete_category(
    category_id: int,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    force: bool | None = None,
) -> None:
    """Delete a budget category upstream and then remove its cached row."""
    await delete_category_service(
        client=client,
        db=db,
        category_id=category_id,
        force=force,
    )
