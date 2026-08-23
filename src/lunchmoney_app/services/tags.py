"""Service logic for tag operations."""

from lunchmoney.models import CreateTagRequestObject, TagObject, UpdateTagRequestObject

from lunchmoney_app.services.operations import OperationContext


async def fetch_tags(context: OperationContext) -> list[TagObject]:
    """Return all tags through the selected reader."""
    return await context.tags.list()


async def fetch_tag_by_id(context: OperationContext, tag_id: int) -> TagObject | None:
    """Return one tag when available."""
    return await context.tags.get(tag_id)


async def create_tag(
    context: OperationContext, request: CreateTagRequestObject
) -> TagObject:
    """Create a tag upstream, then apply mode-specific projection."""
    tag = await context.client.client.tags.create_tag(create_tag_request_object=request)
    await context.project("tags", context.tags.store(tag))
    return tag


async def update_tag(
    context: OperationContext,
    tag_id: int,
    request: UpdateTagRequestObject,
) -> TagObject:
    """Update a tag upstream, then apply mode-specific projection."""
    tag = await context.client.client.tags.update_tag(
        id=tag_id, update_tag_request_object=request
    )
    await context.project("tags", context.tags.store(tag))
    return tag


async def delete_tag(
    context: OperationContext,
    tag_id: int,
    force: bool | None = None,
) -> None:
    """Delete a tag upstream, then reconcile selected state."""
    await context.client.client.tags.delete_tag(id=tag_id, force=force)
    await context.project("tags", context.tags.delete(tag_id))
