"""Service logic for category operations."""

from lunchmoney.models import (
    CategoryObject,
    ChildCategoryObject,
    CreateCategoryRequestObject,
    UpdateCategoryRequestObject,
)

from lunchmoney_app.schemas import CategoryQuery
from lunchmoney_app.services.operations import OperationContext


async def fetch_categories(
    context: OperationContext, query: CategoryQuery
) -> list[CategoryObject]:
    """Return categories through the selected reader."""
    return await context.categories.list(query)


async def fetch_category_by_id(
    context: OperationContext, category_id: int
) -> CategoryObject | ChildCategoryObject | None:
    """Return one category when available."""
    return await context.categories.get(category_id)


async def create_category(
    context: OperationContext,
    request: CreateCategoryRequestObject,
) -> CategoryObject:
    """Create a category upstream, then apply mode-specific projection."""
    category = await context.client.client.categories.create_category(
        create_category_request_object=request
    )
    await context.project("categories", context.categories.store(category))
    return category


async def update_category(
    context: OperationContext,
    category_id: int,
    request: UpdateCategoryRequestObject,
) -> CategoryObject:
    """Update a category upstream, then apply mode-specific projection."""
    category = await context.client.client.categories.update_category(
        id=category_id,
        update_category_request_object=request,
    )
    await context.project("categories", context.categories.store(category))
    return category


async def delete_category(
    context: OperationContext,
    category_id: int,
    force: bool | None = None,
) -> None:
    """Delete a category upstream, then reconcile selected state."""
    await context.client.client.categories.delete_category(id=category_id, force=force)
    await context.project("categories", context.categories.delete(category_id))
