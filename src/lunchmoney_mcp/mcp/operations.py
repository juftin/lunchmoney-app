"""FastMCP middleware that binds the shared data-operation lifecycle."""

from typing import Any

from fastmcp.server.middleware.middleware import CallNext, Middleware, MiddlewareContext

from lunchmoney_mcp.app.dependencies import get_lunchmoney_app, get_shared_database
from lunchmoney_mcp.config import get_settings
from lunchmoney_mcp.services.operations import data_operation


class DataOperationMiddleware(Middleware):
    """Refresh and bind the configured database for each MCP data operation."""

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        """Bind storage for a tool invocation."""
        async with data_operation(
            client=get_lunchmoney_app(),
            database=None if get_settings().ephemeral else get_shared_database(),
        ):
            return await call_next(context)

    async def on_read_resource(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        """Bind storage for a resource read."""
        async with data_operation(
            client=get_lunchmoney_app(),
            database=None if get_settings().ephemeral else get_shared_database(),
        ):
            return await call_next(context)
