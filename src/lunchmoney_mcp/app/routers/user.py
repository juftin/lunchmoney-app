"""User data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import select

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.database.models import User
from lunchmoney_mcp.schemas import UserInfo

router = APIRouter(tags=["User"])


@router.get(
    path="/user",
    response_model=UserInfo | None,
    operation_id="get_user_info",
)
async def get_user_info(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> UserInfo | None:
    """Fetch the authenticated user profile and budget details."""
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
