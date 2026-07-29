"""FastMCP server entrypoint registering modular domain tools."""

import sys

from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.mcp.tools import (
    accounts,
    categories,
    spending,
    sync,
    transactions,
    user,
)

# Explicitly reference imported tool modules to ensure registration
_ = (accounts, categories, spending, sync, transactions, user)


def main() -> None:
    """Launch the FastMCP server entrypoint supporting stdio and sse transports."""
    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)


__all__ = ["main", "mcp"]
