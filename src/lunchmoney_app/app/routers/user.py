"""User data endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from lunchmoney.models import UserObject

from lunchmoney_app.app.dependencies import OperationContext, get_operation_context
from lunchmoney_app.services import fetch_user_info

router = APIRouter(tags=["User"])


@router.get(
    path="/user", response_model=UserObject | None, operation_id="get_user_info"
)
async def get_user_info(
    context: Annotated[OperationContext, Depends(dependency=get_operation_context)],
) -> UserObject | None:
    """Return the authenticated Lunch Money user."""
    return await fetch_user_info(context)
