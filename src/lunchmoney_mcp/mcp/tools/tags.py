"""FastMCP tools for synchronized transaction tag queries."""

from typing import TYPE_CHECKING

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import TagInfo
from lunchmoney_mcp.services import fetch_tag_by_id, fetch_tags

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyDatabase


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
