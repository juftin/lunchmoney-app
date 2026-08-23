"""Category endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import (
    CategoryObject,
    ChildCategoryObject,
    CreateCategoryRequestObject,
    UpdateCategoryRequestObject,
)

from lunchmoney_app.app.dependencies import OperationContext, get_operation_context
from lunchmoney_app.schemas import CategoryQuery
from lunchmoney_app.services import (
    create_category as create_category_service,
    delete_category as delete_category_service,
    fetch_categories,
    fetch_category_by_id,
    update_category as update_category_service,
)

router = APIRouter(tags=["Categories"])


@router.get(
    path="/categories",
    response_model=list[CategoryObject],
    operation_id="list_categories",
)
async def list_categories(
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
    query: Annotated[CategoryQuery, Depends()],
) -> list[CategoryObject]:
    """List categories with the requested hierarchy controls."""
    return await fetch_categories(context, query)


@router.get(
    path="/categories/{category_id}",
    response_model=CategoryObject | ChildCategoryObject | None,
    operation_id="get_category",
)
async def get_category(
    category_id: int,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> CategoryObject | ChildCategoryObject | None:
    """Return one category when available."""
    return await fetch_category_by_id(context, category_id)


@router.post(
    path="/categories", response_model=CategoryObject, operation_id="create_category"
)
async def create_category(
    request: CreateCategoryRequestObject,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> CategoryObject:
    """Create a budget category."""
    return await create_category_service(context, request)


@router.put(
    path="/categories/{category_id}",
    response_model=CategoryObject,
    operation_id="update_category",
)
async def update_category(
    category_id: int,
    request: UpdateCategoryRequestObject,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> CategoryObject:
    """Update a budget category."""
    return await update_category_service(context, category_id, request)


@router.delete(
    path="/categories/{category_id}", status_code=204, operation_id="delete_category"
)
async def delete_category(
    category_id: int,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
    force: bool | None = None,
) -> None:
    """Delete a budget category."""
    await delete_category_service(context, category_id, force)
