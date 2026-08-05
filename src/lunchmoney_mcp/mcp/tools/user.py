"""FastMCP tools for user profile and budget information operations."""

from typing import TYPE_CHECKING

from lunchmoney.models import UserObject

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.services import fetch_user_info

if TYPE_CHECKING:
    from lunchmoney_mcp import LunchMoneyDatabase


@mcp.tool()
async def get_user_info() -> UserObject | None:
    """Fetch the authenticated user profile and budget details.

    Returns
    -------
    UserObject | None
        User profile details or None if no user profile exists in database.
    """
    db: LunchMoneyDatabase = get_database()
    return await fetch_user_info(db=db)


__all__ = ["get_user_info"]
