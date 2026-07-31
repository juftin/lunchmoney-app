"""Tests for the command-line process dispatcher."""

from unittest.mock import AsyncMock, Mock

import pytest


def test_cli_runs_standalone_mcp_without_persistent_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch explicit MCP transport arguments through its ephemeral runtime."""
    import lunchmoney_mcp.cli as cli

    mcp_parser = Mock()
    transport_arguments = Mock()
    mcp_parser.parse_args.return_value = transport_arguments
    settings = Mock()
    parse_cli_settings = Mock(return_value=settings)
    configure_runtime_settings = Mock()
    configure_runtime_mode = Mock()
    configure_auth = Mock()
    run_from_args = Mock()
    monkeypatch.setattr(
        cli.mcp_server,
        "create_argument_parser",
        Mock(return_value=mcp_parser),
    )
    monkeypatch.setattr(cli.mcp_server, "run_from_args", run_from_args)
    monkeypatch.setattr(cli, "parse_cli_settings", parse_cli_settings)
    monkeypatch.setattr(cli, "configure_runtime_settings", configure_runtime_settings)
    monkeypatch.setattr(cli, "configure_runtime_mode", configure_runtime_mode)
    monkeypatch.setattr(cli.mcp_server, "configure_auth", configure_auth)

    cli.main(["mcp", "--stdio"])

    parse_cli_settings.assert_called_once_with(["--stdio"], root_parser=mcp_parser)
    configure_runtime_settings.assert_called_once_with(settings)
    configure_runtime_mode.assert_called_once_with("mcp")
    configure_auth.assert_called_once_with(settings)
    mcp_parser.parse_args.assert_called_once_with(["--stdio"])
    run_from_args.assert_called_once_with(mcp_parser, transport_arguments)


def test_cli_runs_scheduler_with_pydantic_runtime_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch the scheduler while Pydantic Settings owns its runtime flags."""
    import lunchmoney_mcp.cli as cli

    run_schedule_process = AsyncMock()
    monkeypatch.setattr(cli, "run_schedule_process", run_schedule_process)
    settings = Mock()
    parse_cli_settings = Mock(return_value=settings)
    configure_runtime_settings = Mock()
    monkeypatch.setattr(cli, "parse_cli_settings", parse_cli_settings)
    monkeypatch.setattr(cli, "configure_runtime_settings", configure_runtime_settings)

    cli.main(
        [
            "schedule",
            "--scheduler-cron",
            "15 4 * * 1-5",
            "--scheduler-timezone",
            "America/Denver",
        ]
    )

    parse_cli_settings.assert_called_once_with(
        [
            "--scheduler-cron",
            "15 4 * * 1-5",
            "--scheduler-timezone",
            "America/Denver",
        ]
    )
    configure_runtime_settings.assert_called_once_with(settings)
    run_schedule_process.assert_awaited_once_with(settings=settings)


def test_cli_runs_fastapi_with_pydantic_runtime_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass Pydantic Settings CLI flags to the local FastAPI runtime."""
    import lunchmoney_mcp.cli as cli

    settings = Mock(server_host="0.0.0.0", server_port=9000)
    parse_cli_settings = Mock(return_value=settings)
    configure_runtime_settings = Mock()
    export_runtime_settings = Mock()
    run = Mock()
    monkeypatch.setattr(cli, "parse_cli_settings", parse_cli_settings)
    monkeypatch.setattr(cli, "configure_runtime_settings", configure_runtime_settings)
    monkeypatch.setattr(cli, "export_runtime_settings", export_runtime_settings)
    monkeypatch.setattr(cli.uvicorn, "run", run)

    cli.main(["serve", "--server-host", "0.0.0.0", "--server-port", "9000"])

    parse_cli_settings.assert_called_once_with(
        ["--server-host", "0.0.0.0", "--server-port", "9000"]
    )
    configure_runtime_settings.assert_called_once_with(settings)
    export_runtime_settings.assert_called_once_with(settings)
    run.assert_called_once_with(
        "lunchmoney_mcp.app.main:app",
        host="0.0.0.0",
        port=9000,
        reload=True,
    )
