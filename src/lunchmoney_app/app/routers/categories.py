"""Categories data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import (
    CategoryObject,
    ChildCategoryObject,
    CreateCategoryRequestObject,
    UpdateCategoryRequestObject,
)

from lunchmoney_app.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.config import get_settings
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.schemas import CategoryQuery
from lunchmoney_app.services import (
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
    response_model=list[CategoryObject],
    operation_id="list_categories",
)
async def list_categories(
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    query: Annotated[CategoryQuery, Depends()],
) -> list[CategoryObject]:
    """List categories using Lunch Money's hierarchy and group controls.

    **Parameters:**

    - **client**: Lunch Money client used in stateless mode.
    - **db**: Database manager instance used in persistent mode.
    - **query**: Upstream-compatible category collection controls.

    **Returns:** Matching category objects in the requested representation.
    """
    return await fetch_categories(
        client=client,
        db=db,
        query=query,
        live=get_settings().stateless,
    )


@router.get(
    path="/categories/{category_id}",
    response_model=CategoryObject | ChildCategoryObject | None,
    operation_id="get_category",
)
async def get_category(
    category_id: int,
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> CategoryObject | ChildCategoryObject | None:
    """Fetch one synchronized budget category.

    **Parameters:**

    - **category_id**: Identifier of the category to retrieve.
    - **db**: Database manager instance.

    **Returns:** Matching category, or `None` when it has not been synchronized.
    """
    return await fetch_category_by_id(db=db, category_id=category_id)


@router.post(
    path="/categories",
    response_model=CategoryObject,
    operation_id="create_category",
)
async def create_category(
    request: CreateCategoryRequestObject,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> CategoryObject:
    """Create a budget category and store Lunch Money's canonical response."""
    return await create_category_service(client=client, db=db, request=request)


@router.put(
    path="/categories/{category_id}",
    response_model=CategoryObject,
    operation_id="update_category",
)
async def update_category(
    category_id: int,
    request: UpdateCategoryRequestObject,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> CategoryObject:
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
