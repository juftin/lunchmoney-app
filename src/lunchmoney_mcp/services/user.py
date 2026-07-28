"""Service logic for User data operations."""

from sqlmodel import select

from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import User
from lunchmoney_mcp.schemas import UserInfo


async def fetch_user_info(db: LunchMoneyDatabase) -> UserInfo | None:
    """Fetch user profile details from database.

    Parameters
    ----------
    db : LunchMoneyDatabase
        Database manager instance.

    Returns
    -------
    UserInfo | None
        User profile details or None if no user exists.
    """
    async with db.session() as session:
        result = await session.exec(select(User))
        user = result.first()
        if user is None:
            return None
        return UserInfo(
            id=user.id,
            name=user.name,
            email=user.email,
            budget_name=user.budget_name,
            primary_currency=user.primary_currency,
        )
