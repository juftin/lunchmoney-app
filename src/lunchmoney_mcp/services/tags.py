"""Service logic for synchronized Lunch Money tag queries."""

from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Tag
from lunchmoney_mcp.schemas import TagInfo


def _tag_info(tag: Tag) -> TagInfo:
    """Convert a persisted tag into the public read-only response schema."""
    return TagInfo(
        id=tag.id,
        name=tag.name,
        description=tag.description,
        text_color=tag.text_color,
        background_color=tag.background_color,
        archived=tag.archived,
    )


async def fetch_tags(db: LunchMoneyDatabase) -> list[TagInfo]:
    """Fetch all synchronized transaction tags.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    list[TagInfo]
        All tags in identifier order.
    """
    return [_tag_info(tag) for tag in await db.list(Tag)]


async def fetch_tag_by_id(
    db: LunchMoneyDatabase,
    tag_id: int,
) -> TagInfo | None:
    """Fetch one synchronized transaction tag by identifier.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.
    tag_id : int
        Identifier of the tag to retrieve.

    Returns
    -------
    TagInfo | None
        Matching tag, or ``None`` when it has not been synchronized.
    """
    tag = await db.get(Tag, tag_id)
    return _tag_info(tag) if tag is not None else None
