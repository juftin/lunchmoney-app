"""FastMCP user tools."""

from lunchmoney.models import UserObject

from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.services import fetch_user_info
from lunchmoney_app.services.operations import get_operation_context


@mcp.tool()
async def get_user_info() -> UserObject | None:
    """Return the authenticated Lunch Money user."""
    return await fetch_user_info(get_operation_context())


__all__ = ["get_user_info"]
