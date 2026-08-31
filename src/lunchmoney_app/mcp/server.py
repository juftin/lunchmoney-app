"""FastMCP server entrypoint registering modular domain tools."""

import argparse
import datetime
import json
import sys
from typing import Literal, cast

from lunchmoney_app.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_app.app.auth import get_mcp_oauth_provider
from lunchmoney_app.config import (
    McpCliSettings,
    RuntimeSettings,
    configure_runtime_mode,
    configure_runtime_settings,
    get_settings,
    parse_cli_settings,
)
from lunchmoney_app.mcp.app import mcp
from lunchmoney_app.schemas import CategoryQuery
from lunchmoney_app.mcp.tools import (
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
from lunchmoney_app.services import fetch_account_summary, fetch_categories


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


@mcp.prompt(
    name="unreviewed_transactions_review",
    description="Review unreviewed transactions and apply confirmed corrections.",
)
def unreviewed_transactions_review() -> str:
    """Provide a repeatable workflow for reviewing unreviewed transactions."""
    return (
        "Default to the previous 45 days, unless the user supplies a different "
        "period. Call review_transactions to retrieve the unreviewed transaction "
        "queue with Plaid metadata, category choices, and account context. Inspect "
        "each transaction's plaid_metadata alongside its payee, original_name, "
        "amount, date, category, and linked account. Recommend a category, "
        "corrected payee when needed, and useful notes for each transaction. Do "
        "not make changes until the user confirms the exact transaction IDs and "
        "values. For each confirmed transaction, call bulk_update_transactions "
        "with only its confirmed category_id, notes, and payee changes plus "
        "status='reviewed'. Report the returned transactions."
    )


def create_argument_parser() -> argparse.ArgumentParser:
    """Create the transport parser used by the standalone MCP command."""
    parser = argparse.ArgumentParser(
        description="Launch Lunch Money MCP over stdio or a remote HTTP endpoint."
    )
    transport_group = parser.add_mutually_exclusive_group()
    transport_group.add_argument(
        "--stdio",
        action="store_const",
        const="stdio",
        dest="transport",
        help="Local client transport; no listening socket or retained data (default).",
    )
    transport_group.add_argument(
        "--sse",
        action="store_const",
        const="sse",
        dest="transport",
        help="Compatibility Server-Sent Events endpoint at /sse (persistent default).",
    )
    transport_group.add_argument(
        "--http",
        action="store_const",
        const="http",
        dest="transport",
        help="Compatibility HTTP endpoint at /mcp (persistent default).",
    )
    transport_group.add_argument(
        "--streamable-http",
        action="store_const",
        const="streamable-http",
        dest="transport",
        help="Remote Streamable HTTP endpoint at /mcp (persistent default).",
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


def apply_transport_defaults(
    settings: RuntimeSettings,
    args: argparse.Namespace,
) -> RuntimeSettings:
    """Apply MCP storage defaults after the transport has been selected.

    Stdio is normally launched as a child process for one local MCP client, so
    each request passes through to Lunch Money without retained data. Long-lived
    HTTP transports retain data unless the operator selects another mode.

    Parameters
    ----------
    settings : RuntimeSettings
        Configuration resolved from the command line and environment.
    args : argparse.Namespace
        Parsed MCP transport arguments.

    Returns
    -------
    RuntimeSettings
        Settings with the stdio-only ephemeral default applied when appropriate.
    """
    persistence_fields = {"stateless", "ephemeral"}
    if (
        args.transport or "stdio"
    ) == "stdio" and not persistence_fields & settings.model_fields_set:
        settings.ephemeral = True
    return settings


def main(argv: list[str] | None = None) -> None:
    """Launch the FastMCP server with the transport selected by a CLI flag."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = create_argument_parser()
    settings = parse_cli_settings(arguments, McpCliSettings, root_parser=parser)
    parsed_arguments = parser.parse_args(arguments)
    settings = apply_transport_defaults(settings, parsed_arguments)
    configure_runtime_settings(settings)
    configure_runtime_mode("mcp")
    configure_auth(settings)
    run_from_args(parser, parsed_arguments, settings)


__all__ = [
    "configure_auth",
    "create_argument_parser",
    "apply_transport_defaults",
    "main",
    "mcp",
    "run_from_args",
]
