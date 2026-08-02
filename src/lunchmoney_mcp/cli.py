"""Command-line entrypoint for the MCP, FastAPI, and scheduler runtimes."""

from __future__ import annotations

import argparse
import asyncio
import sys

import uvicorn

from lunchmoney_mcp.config import (
    McpCliSettings,
    ScheduleCliSettings,
    ServeCliSettings,
    configure_runtime_mode,
    configure_runtime_settings,
    export_runtime_settings,
    parse_cli_settings,
)
from lunchmoney_mcp.logging_config import LOG_CONFIG
from lunchmoney_mcp.mcp import server as mcp_server
from lunchmoney_mcp.scheduler import run_schedule_process


def main(argv: list[str] | None = None) -> None:
    """Dispatch one dedicated MCP, FastAPI, or scheduler runtime command.

    Parameters
    ----------
    argv : list[str] | None
        Optional command arguments without the executable name. Defaults to sys.argv.
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Lunch Money MCP runtime commands.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "mcp",
        help="Run the standalone MCP server.",
        add_help=False,
    )
    commands.add_parser(
        "schedule",
        help="Run the opt-in scheduler using Pydantic settings CLI flags.",
        add_help=False,
    )
    commands.add_parser(
        "serve",
        help="Run local FastAPI using Pydantic settings CLI flags.",
        add_help=False,
    )
    parsed, runtime_arguments = parser.parse_known_args(arguments)
    if parsed.command == "mcp":
        mcp_parser = mcp_server.create_argument_parser()
        settings = parse_cli_settings(
            runtime_arguments,
            McpCliSettings,
            root_parser=mcp_parser,
        )
        configure_runtime_settings(settings)
        configure_runtime_mode("mcp")
        mcp_server.configure_auth(settings)
        mcp_server.run_from_args(
            mcp_parser,
            mcp_parser.parse_args(runtime_arguments),
            settings,
        )
        return
    if parsed.command == "schedule":
        settings = parse_cli_settings(runtime_arguments, ScheduleCliSettings)
        configure_runtime_settings(settings)
        configure_runtime_mode("schedule")
        asyncio.run(run_schedule_process(settings=settings))
        return

    settings = parse_cli_settings(runtime_arguments, ServeCliSettings)
    configure_runtime_settings(settings)
    configure_runtime_mode("serve")
    export_runtime_settings(settings)
    uvicorn.run(
        "lunchmoney_mcp.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_config=LOG_CONFIG,
    )


__all__ = ["main"]
