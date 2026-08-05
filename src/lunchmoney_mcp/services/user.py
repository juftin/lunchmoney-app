"""Service logic for User data operations."""

from lunchmoney.models import UserObject
from sqlmodel import select

from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import User


async def fetch_user_info(db: LunchMoneyDatabase) -> UserObject | None:
    """Fetch user profile details from database.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    UserObject | None
        User profile details or None if no user exists.
    """
    async with db.session() as session:
        result = await session.exec(select(User))
        user = result.first()
        if user is None:
            return None
        return user.to_api()
