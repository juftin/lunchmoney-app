"""User data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lunchmoney_mcp.app.dependencies import get_database
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.schemas import UserInfo
from lunchmoney_mcp.services import fetch_user_info

router = APIRouter(tags=["User"])
"""FastAPI APIRouter for user profile endpoints."""


@router.get(
    path="/user",
    response_model=UserInfo | None,
    operation_id="get_user_info",
)
async def get_user_info(
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
) -> UserInfo | None:
    """Fetch the authenticated user profile and budget details.

    **Parameters:**

    - **db**: Database manager instance.

    **Returns:** User profile details, or `None` if no user profile has been synced.
    """
    return await fetch_user_info(db=db)
