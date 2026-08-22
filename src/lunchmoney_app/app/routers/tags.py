"""Transaction tag data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import (
    CreateTagRequestObject,
    TagObject,
    UpdateTagRequestObject,
)

from lunchmoney_app.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_app.client import LunchMoneyApp
from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.services import (
    create_tag as create_tag_service,
    delete_tag as delete_tag_service,
    fetch_tag_by_id,
    fetch_tags,
    update_tag as update_tag_service,
)

router = APIRouter(tags=["Tags"])
"""FastAPI APIRouter for synchronized transaction tag endpoints."""


@router.get(path="/tags", response_model=list[TagObject], operation_id="list_tags")
async def list_tags(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> list[TagObject]:
    """List all synchronized transaction tags.

    **Parameters:**

    - **db**: Database manager instance.

    **Returns:** Complete synchronized transaction tags.
    """
    return await fetch_tags(db=db)


@router.get(
    path="/tags/{tag_id}", response_model=TagObject | None, operation_id="get_tag"
)
async def get_tag(
    tag_id: int,
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> TagObject | None:
    """Fetch one synchronized transaction tag.

    **Parameters:**

    - **tag_id**: Identifier of the tag to retrieve.
    - **db**: Database manager instance.

    **Returns:** Matching tag, or `None` when it has not been synchronized.
    """
    return await fetch_tag_by_id(db=db, tag_id=tag_id)


@router.post(path="/tags", response_model=TagObject, operation_id="create_tag")
async def create_tag(
    request: CreateTagRequestObject,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> TagObject:
    """Create a transaction tag and store Lunch Money's canonical response."""
    return await create_tag_service(client=client, db=db, request=request)


@router.put(
    path="/tags/{tag_id}",
    response_model=TagObject,
    operation_id="update_tag",
)
async def update_tag(
    tag_id: int,
    request: UpdateTagRequestObject,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> TagObject:
    """Update a transaction tag and store Lunch Money's canonical response."""
    return await update_tag_service(
        client=client,
        db=db,
        tag_id=tag_id,
        request=request,
    )


@router.delete(path="/tags/{tag_id}", status_code=204, operation_id="delete_tag")
async def delete_tag(
    tag_id: int,
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    force: bool | None = None,
) -> None:
    """Delete a transaction tag upstream and then remove it from the cache."""
    await delete_tag_service(
        client=client,
        db=db,
        tag_id=tag_id,
        force=force,
    )
