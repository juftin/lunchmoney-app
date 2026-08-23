"""Service logic for user data operations."""

from lunchmoney.models import UserObject

from lunchmoney_app.services.operations import OperationContext


async def fetch_user_info(context: OperationContext) -> UserObject | None:
    """Return the authenticated user through the selected reader."""
    return await context.user.get()
