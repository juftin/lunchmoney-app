"""Server-rendered financial dashboard endpoint."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.client import LunchMoneyApp
from lunchmoney_mcp.database import LunchMoneyDatabase
from lunchmoney_mcp.services.dashboard import fetch_dashboard_data


router = APIRouter(tags=["Dashboard"])
"""FastAPI APIRouter for the authenticated financial dashboard."""

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
"""HTML templates used by dashboard routes."""


@router.get(
    path="/",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def dashboard(
    request: Request,
    db: Annotated[LunchMoneyDatabase, Depends(dependency=get_database)],
    client: Annotated[LunchMoneyApp, Depends(dependency=get_lunchmoney_app)],
) -> HTMLResponse:
    """Render the authenticated, read-only Lunch Money dashboard."""
    data = await fetch_dashboard_data(db=db, client=client)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"dashboard": data},
    )


__all__ = ["router"]
