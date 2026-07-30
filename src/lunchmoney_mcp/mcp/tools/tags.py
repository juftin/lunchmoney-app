"""FastMCP tools for synchronized transaction tag operations."""

from typing import TYPE_CHECKING

from lunchmoney.models import CreateTagRequestObject, UpdateTagRequestObject

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import TagInfo
from lunchmoney_mcp.services import (
    create_tag as create_tag_service,
    delete_tag as delete_tag_service,
    fetch_tag_by_id,
    fetch_tags,
    update_tag as update_tag_service,
)

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyApp, LunchMoneyDatabase


@mcp.tool()
async def list_tags() -> list[TagInfo]:
    """List all synchronized transaction tags.

    Returns
    -------
    list[TagInfo]
        All synchronized transaction tags.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_tags(db=db)


@mcp.tool()
async def get_tag(tag_id: int) -> TagInfo | None:
    """Fetch one synchronized transaction tag.

    Parameters
    ----------
    tag_id : int
        Identifier of the tag to retrieve.

    Returns
    -------
    TagInfo | None
        Matching tag, or ``None`` when it has not been synchronized.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_tag_by_id(db=db, tag_id=tag_id)


@mcp.tool()
async def create_tag(request: CreateTagRequestObject) -> TagInfo:
    """Create a transaction tag and cache Lunch Money's canonical response."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await create_tag_service(client=client, db=db, request=request)


@mcp.tool()
async def update_tag(
    tag_id: int,
    request: UpdateTagRequestObject,
) -> TagInfo:
    """Update a transaction tag and cache Lunch Money's canonical response."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    return await update_tag_service(
        client=client,
        db=db,
        tag_id=tag_id,
        request=request,
    )


@mcp.tool()
async def delete_tag(tag_id: int, force: bool | None = None) -> None:
    """Delete a transaction tag upstream and remove it from the local cache."""
    client: LunchMoneyApp = get_lunchmoney_app()
    db: LunchMoneyDatabase = get_database()
    await delete_tag_service(client=client, db=db, tag_id=tag_id, force=force)


__all__ = [
    "create_tag",
    "delete_tag",
    "get_tag",
    "list_tags",
    "update_tag",
]
