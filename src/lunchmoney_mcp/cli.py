"""Command-line entrypoint for the MCP, FastAPI, and scheduler runtimes."""

from __future__ import annotations

import argparse
import asyncio
import sys

import uvicorn
from pydantic import ValidationError

from lunchmoney_mcp.__about__ import __application__, __version__
from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.config import (
    McpCliSettings,
    ScheduleCliSettings,
    ServeCliSettings,
    SyncCliSettings,
    configure_runtime_mode,
    configure_runtime_settings,
    get_secret_settings,
    export_runtime_settings,
    parse_cli_settings,
)
from lunchmoney_mcp.doctor import build_doctor_report
from lunchmoney_mcp.logging_config import LOG_CONFIG
from lunchmoney_mcp.mcp import server as mcp_server
from lunchmoney_mcp.scheduler import run_schedule_process
from lunchmoney_mcp.services import execute_sync


def main(argv: list[str] | None = None) -> None:
    """Dispatch one dedicated MCP, FastAPI, scheduler, or operator command.

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
    commands.add_parser(
        "sync",
        help="Run one foreground synchronization.",
        add_help=False,
    )
    commands.add_parser(
        "doctor",
        help="Check local configuration without external network requests.",
        add_help=False,
    )
    commands.add_parser(
        "version",
        help="Print the installed package version.",
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
    if parsed.command == "sync":
        sync_parser = _create_sync_parser()
        settings = parse_cli_settings(
            runtime_arguments,
            SyncCliSettings,
            root_parser=sync_parser,
        )
        configure_runtime_settings(settings)
        configure_runtime_mode("sync")
        sync_arguments = sync_parser.parse_args(runtime_arguments)
        asyncio.run(
            _run_sync(
                days=sync_arguments.days,
                incremental=sync_arguments.incremental,
                safety_margin_minutes=settings.sync_safety_margin_minutes,
            )
        )
        return
    if parsed.command == "doctor":
        doctor_parser = _create_doctor_parser()
        doctor_parser.parse_args(runtime_arguments)
        try:
            settings = parse_cli_settings([], ServeCliSettings)
        except ValidationError:
            doctor_parser.error("invalid local configuration")
        report = build_doctor_report(
            settings=settings,
            secret_settings=get_secret_settings(),
        )
        print(report.render())
        if not report.is_healthy:
            raise SystemExit(1)
        return
    if parsed.command == "version":
        _create_version_parser().parse_args(runtime_arguments)
        print(f"{__application__} {__version__}")
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


def _create_sync_parser() -> argparse.ArgumentParser:
    """Create the command-specific parser for a single foreground sync.

    Returns
    -------
    argparse.ArgumentParser
        Parser defining operation-specific, non-secret sync arguments.
    """
    parser = argparse.ArgumentParser(description="Synchronize Lunch Money data once.")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        choices=range(1, 367),
        metavar="DAYS",
        help="Rolling transaction window for the initial synchronization (default: 30).",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Resume transaction synchronization from its saved watermark.",
    )
    return parser


def _create_doctor_parser() -> argparse.ArgumentParser:
    """Create the command-specific parser for local diagnostics."""
    return argparse.ArgumentParser(
        description="Check local configuration without network requests."
    )


def _create_version_parser() -> argparse.ArgumentParser:
    """Create the command-specific parser for package version output."""
    return argparse.ArgumentParser(description="Print the installed package version.")


async def _run_sync(
    days: int,
    incremental: bool,
    safety_margin_minutes: int,
) -> None:
    """Execute one sync and print its concise result.

    Parameters
    ----------
    days : int
        Initial rolling transaction window.
    incremental : bool
        Whether transaction refresh uses the existing watermark.
    safety_margin_minutes : int
        Overlap applied to an incremental transaction refresh.
    """
    response = await execute_sync(
        db=get_database(),
        client=get_lunchmoney_app(),
        days=days,
        incremental=incremental,
        safety_margin_minutes=safety_margin_minutes,
    )
    print(response.model_dump_json())


__all__ = ["main"]
