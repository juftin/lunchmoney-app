"""FastMCP category tools."""

from lunchmoney.models import (
    CategoryObject,
    ChildCategoryObject,
    CreateCategoryRequestObject,
    UpdateCategoryRequestObject,
)

from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.schemas import CategoryQuery
from lunchmoney_app.services import (
    create_category as create_service,
    delete_category as delete_service,
    fetch_categories,
    fetch_category_by_id,
    update_category as update_service,
)
from lunchmoney_app.services.operations import get_operation_context


@mcp.tool()
async def list_categories(query: CategoryQuery | None = None) -> list[CategoryObject]:
    """List categories with hierarchy controls."""
    return await fetch_categories(get_operation_context(), query or CategoryQuery())


@mcp.tool()
async def get_category(category_id: int) -> CategoryObject | ChildCategoryObject | None:
    """Return one category when available."""
    return await fetch_category_by_id(get_operation_context(), category_id)


@mcp.tool()
async def create_category(request: CreateCategoryRequestObject) -> CategoryObject:
    """Create a category."""
    return await create_service(get_operation_context(), request)


@mcp.tool()
async def update_category(
    category_id: int, request: UpdateCategoryRequestObject
) -> CategoryObject:
    """Update a category."""
    return await update_service(get_operation_context(), category_id, request)


@mcp.tool()
async def delete_category(category_id: int, force: bool | None = None) -> None:
    """Delete a category."""
    await delete_service(get_operation_context(), category_id, force)


__all__ = [
    "create_category",
    "delete_category",
    "get_category",
    "list_categories",
    "update_category",
]
