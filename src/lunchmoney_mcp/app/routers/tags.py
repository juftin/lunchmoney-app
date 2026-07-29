"""Transaction tag data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import TagInfo
from lunchmoney_mcp.services import fetch_tag_by_id, fetch_tags

router = APIRouter(tags=["Tags"])
"""FastAPI APIRouter for synchronized transaction tag endpoints."""


@router.get(path="/tags", response_model=list[TagInfo], operation_id="list_tags")
async def list_tags(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> list[TagInfo]:
    """List all synchronized transaction tags.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    list[TagInfo]
        All synchronized transaction tags.
    """
    return await fetch_tags(db=db)


@router.get(
    path="/tags/{tag_id}", response_model=TagInfo | None, operation_id="get_tag"
)
async def get_tag(
    tag_id: int,
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> TagInfo | None:
    """Fetch one synchronized transaction tag.

    Parameters
    ----------
    tag_id : int
        Identifier of the tag to retrieve.
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    TagInfo | None
        Matching tag, or ``None`` when it has not been synchronized.
    """
    return await fetch_tag_by_id(db=db, tag_id=tag_id)
