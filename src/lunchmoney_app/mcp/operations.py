"""FastMCP middleware that binds the shared data-operation lifecycle."""

import json
from typing import Any

from fastmcp.server.middleware.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult
from mcp.types import TextContent

from lunchmoney_app.app.dependencies import get_lunchmoney_app, get_shared_database
from lunchmoney_app.config import get_settings
from lunchmoney_app.services.operations import (
    EphemeralOperationContextFactory,
    OperationContext,
    OperationContextFactory,
    StatefulOperationContextFactory,
)
from lunchmoney_app.services.errors import StatefulModeRequired


class DataOperationMiddleware(Middleware):
    """Refresh and bind the configured database for each MCP data operation."""

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        """Bind storage for a tool invocation."""
        try:
            tool_name = getattr(getattr(context, "message", None), "name", None)
            if get_settings().persistence_mode == "ephemeral" and tool_name in {
                "sync_data",
                "get_sync_status",
            }:
                raise StatefulModeRequired
            async with _operation_factory().operation():
                return await call_next(context)
        except StatefulModeRequired as error:
            return ToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(error.as_dict()),
                    )
                ],
                structured_content=error.as_dict(),
                is_error=True,
            )

    async def on_read_resource(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        """Bind storage for a resource read."""
        async with _operation_factory().operation():
            try:
                return await call_next(context)
            except StatefulModeRequired as error:
                raise RuntimeError(json.dumps(error.as_dict())) from None


def _operation_factory() -> OperationContextFactory[OperationContext]:
    """Select the concrete MCP operation factory without optional storage."""
    client = get_lunchmoney_app()
    if get_settings().persistence_mode == "ephemeral":
        return EphemeralOperationContextFactory(client)
    return StatefulOperationContextFactory(client, get_shared_database())
