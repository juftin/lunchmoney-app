"""FastMCP tag tools."""

from lunchmoney.models import CreateTagRequestObject, TagObject, UpdateTagRequestObject

from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.services import (
    create_tag as create_service,
    delete_tag as delete_service,
    fetch_tag_by_id,
    fetch_tags,
    update_tag as update_service,
)
from lunchmoney_app.services.operations import get_operation_context


@mcp.tool()
async def list_tags() -> list[TagObject]:
    """List all tags."""
    return await fetch_tags(get_operation_context())


@mcp.tool()
async def get_tag(tag_id: int) -> TagObject | None:
    """Return one tag when available."""
    return await fetch_tag_by_id(get_operation_context(), tag_id)


@mcp.tool()
async def create_tag(request: CreateTagRequestObject) -> TagObject:
    """Create a tag."""
    return await create_service(get_operation_context(), request)


@mcp.tool()
async def update_tag(tag_id: int, request: UpdateTagRequestObject) -> TagObject:
    """Update a tag."""
    return await update_service(get_operation_context(), tag_id, request)


@mcp.tool()
async def delete_tag(tag_id: int, force: bool | None = None) -> None:
    """Delete a tag."""
    await delete_service(get_operation_context(), tag_id, force)


__all__ = ["create_tag", "delete_tag", "get_tag", "list_tags", "update_tag"]
