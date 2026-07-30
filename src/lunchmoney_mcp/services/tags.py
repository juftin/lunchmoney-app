"""Service logic for synchronized Lunch Money tag operations."""

from lunchmoney.models import (
    CreateTagRequestObject,
    TagObject,
    UpdateTagRequestObject,
)

from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import Tag, Transaction
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


async def _store_tag(db: LunchMoneyDatabase, tag: TagObject) -> TagInfo:
    """Persist an upstream tag response and expose its public fields."""
    stored = await db.upsert(Tag.from_api(tag))
    return _tag_info(stored)


async def create_tag(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    request: CreateTagRequestObject,
) -> TagInfo:
    """Create a tag upstream before saving its canonical response locally."""
    tag = await client.client.tags.create_tag(create_tag_request_object=request)
    return await _store_tag(db=db, tag=tag)


async def update_tag(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    tag_id: int,
    request: UpdateTagRequestObject,
) -> TagInfo:
    """Update a tag upstream before saving its canonical response locally."""
    tag = await client.client.tags.update_tag(
        id=tag_id,
        update_tag_request_object=request,
    )
    return await _store_tag(db=db, tag=tag)


async def delete_tag(
    client: LunchMoneyApp,
    db: LunchMoneyDatabase,
    tag_id: int,
    force: bool | None = None,
) -> None:
    """Delete a tag upstream before removing its cached transaction links."""
    await client.client.tags.delete_tag(id=tag_id, force=force)
    transactions = await db.list(Transaction)
    affected_transactions = [
        transaction
        for transaction in transactions
        if any(link.tag_id == tag_id for link in transaction.tag_links)
    ]
    for transaction in affected_transactions:
        transaction.tag_links = [
            link for link in transaction.tag_links if link.tag_id != tag_id
        ]
        transaction.tags = [tag for tag in transaction.tags if tag.id != tag_id]
    if affected_transactions:
        await db.upsert_many(affected_transactions)
    await db.delete(Tag, tag_id)
