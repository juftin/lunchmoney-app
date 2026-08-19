"""FastMCP server entrypoint registering modular domain tools."""

import argparse
import datetime
import json
import sys
from typing import Literal, cast

from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.app.auth import get_mcp_oauth_provider
from lunchmoney_mcp.config import (
    McpCliSettings,
    RuntimeSettings,
    configure_runtime_mode,
    configure_runtime_settings,
    get_settings,
    parse_cli_settings,
)
from lunchmoney_mcp.mcp.app import mcp
from lunchmoney_mcp.schemas import CategoryQuery
from lunchmoney_mcp.mcp.tools import (
    accounts,
    budgets,
    categories,
    recurring,
    spending,
    summary,
    sync,
    tags,
    transactions,
    user,
)
from lunchmoney_mcp.services import fetch_account_summary, fetch_categories


Transport = Literal["stdio", "http", "sse", "streamable-http"]
"""Transport values accepted by the standalone MCP server."""

# Explicitly reference imported tool modules to ensure registration
_ = (
    accounts,
    budgets,
    categories,
    recurring,
    spending,
    summary,
    sync,
    tags,
    transactions,
    user,
)


@mcp.resource(
    "lunchmoney://summary",
    description="Current-month budget summary with totals.",
    mime_type="text/markdown",
)
async def account_summary_resource() -> str:
    """Render the current month's cached Lunch Money summary as Markdown."""
    today = datetime.date.today()
    summary = await fetch_account_summary(
        db=get_database(),
        client=get_lunchmoney_app(),
        start_date=today.replace(day=1),
        end_date=today,
        include_totals=True,
    )
    if summary is None:
        return (
            "# Lunch Money summary\n\nNo cached summary is available for this period."
        )
    return f"# Lunch Money summary\n\n```json\n{summary.model_dump_json(indent=2)}\n```"


@mcp.resource(
    "lunchmoney://categories",
    description="Complete synchronized category hierarchy.",
    mime_type="application/json",
)
async def categories_resource() -> str:
    """Render configured categories as a flat JSON collection resource."""
    categories = await fetch_categories(
        client=get_lunchmoney_app(),
        db=get_database(),
        query=CategoryQuery(),
        live=get_settings().stateless,
    )
    return json.dumps([category.model_dump(mode="json") for category in categories])


@mcp.prompt(
    name="budget_health_check",
    description="Analyze monthly budget performance and flag over-budget categories.",
)
def budget_health_check() -> str:
    """Provide a repeatable workflow for evaluating the current monthly budget."""
    return (
        "Review the current month's Lunch Money budget summary. Identify categories "
        "that are over budget, explain the largest variances, and recommend practical "
        "adjustments for the remainder of the month."
    )


@mcp.prompt(
    name="uncategorized_transactions_audit",
    description="Find uncategorized transactions and recommend assignments.",
)
def uncategorized_transactions_audit() -> str:
    """Provide a repeatable workflow for auditing uncategorized transactions."""
    return (
        "Find recent uncategorized Lunch Money transactions. Group similar merchants, "
        "recommend the most appropriate existing category for each group, and ask for "
        "confirmation before making any changes."
    )


def create_argument_parser() -> argparse.ArgumentParser:
    """Create the transport parser used by the standalone MCP command."""
    parser = argparse.ArgumentParser(description="Launch the Lunch Money MCP server.")
    transport_group = parser.add_mutually_exclusive_group()
    transport_group.add_argument(
        "--stdio",
        action="store_const",
        const="stdio",
        dest="transport",
        help="Use standard input/output transport (default).",
    )
    transport_group.add_argument(
        "--sse", action="store_const", const="sse", dest="transport"
    )
    transport_group.add_argument(
        "--http", action="store_const", const="http", dest="transport"
    )
    transport_group.add_argument(
        "--streamable-http",
        action="store_const",
        const="streamable-http",
        dest="transport",
    )
    return parser


def configure_auth(settings: RuntimeSettings) -> None:
    """Apply CLI-resolved OAuth configuration before starting FastMCP.

    Parameters
    ----------
    settings : RuntimeSettings
        Runtime configuration containing optional OIDC proxy settings.
    """
    mcp.auth = get_mcp_oauth_provider(settings=settings)


def run_from_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    settings: RuntimeSettings,
) -> None:
    """Run FastMCP using arguments parsed by :func:`create_argument_parser`."""
    transport = cast(Transport, args.transport or "stdio")
    if transport == "stdio":
        if hasattr(args, "host") or hasattr(args, "port"):
            parser.error("--host and --port require an HTTP transport")
        mcp.run(transport=transport)
        return

    mcp.run(transport=transport, host=settings.host, port=settings.port)


def main(argv: list[str] | None = None) -> None:
    """Launch the FastMCP server with the transport selected by a CLI flag."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = create_argument_parser()
    settings = parse_cli_settings(arguments, McpCliSettings, root_parser=parser)
    configure_runtime_settings(settings)
    configure_runtime_mode("mcp")
    configure_auth(settings)
    run_from_args(parser, parser.parse_args(arguments), settings)


__all__ = [
    "configure_auth",
    "create_argument_parser",
    "main",
    "mcp",
    "run_from_args",
]
