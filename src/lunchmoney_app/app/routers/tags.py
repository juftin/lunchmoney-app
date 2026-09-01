"""Transaction tag endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import CreateTagRequestObject, TagObject, UpdateTagRequestObject

from lunchmoney_app.app.dependencies import OperationContext, get_operation_context
from lunchmoney_app.services import (
    create_tag as create_tag_service,
    delete_tag as delete_tag_service,
    fetch_tag_by_id,
    fetch_tags,
    update_tag as update_tag_service,
)

router = APIRouter(tags=["Tags"])


@router.get(path="/tags", response_model=list[TagObject], operation_id="list_tags")
async def list_tags(
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> list[TagObject]:
    """List all transaction tags."""
    return await fetch_tags(context)


@router.get(
    path="/tags/{tag_id}", response_model=TagObject | None, operation_id="get_tag"
)
async def get_tag(
    tag_id: int,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> TagObject | None:
    """Return one tag when available."""
    return await fetch_tag_by_id(context, tag_id)


@router.post(path="/tags", response_model=TagObject, operation_id="create_tag")
async def create_tag(
    request: CreateTagRequestObject,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> TagObject:
    """Create a transaction tag."""
    return await create_tag_service(context, request)


@router.put(path="/tags/{tag_id}", response_model=TagObject, operation_id="update_tag")
async def update_tag(
    tag_id: int,
    request: UpdateTagRequestObject,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> TagObject:
    """Update a transaction tag."""
    return await update_tag_service(context, tag_id, request)


@router.delete(path="/tags/{tag_id}", status_code=204, operation_id="delete_tag")
async def delete_tag(
    tag_id: int,
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
    force: bool | None = None,
) -> None:
    """Delete a transaction tag."""
    await delete_tag_service(context, tag_id, force)
