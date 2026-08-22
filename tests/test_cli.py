"""Tests for the command-line process dispatcher."""

from unittest.mock import ANY, AsyncMock, Mock

import pytest

from lunchmoney_app.config import (
    McpCliSettings,
    ScheduleCliSettings,
    ServeCliSettings,
    SyncCliSettings,
)


def test_cli_runs_standalone_mcp_without_persistent_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch explicit MCP transport arguments through its ephemeral runtime."""
    import lunchmoney_app.cli as cli

    mcp_parser = Mock()
    transport_arguments = Mock()
    mcp_parser.parse_args.return_value = transport_arguments
    settings = Mock()
    parse_cli_settings = Mock(return_value=settings)
    configure_runtime_settings = Mock()
    configure_runtime_mode = Mock()
    configure_auth = Mock()
    run_from_args = Mock()
    apply_transport_defaults = Mock(return_value=settings)
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
    monkeypatch.setattr(
        cli.mcp_server,
        "apply_transport_defaults",
        apply_transport_defaults,
    )

    cli.main(["mcp", "--stdio"])

    parse_cli_settings.assert_called_once_with(
        ["--stdio"],
        McpCliSettings,
        root_parser=mcp_parser,
    )
    apply_transport_defaults.assert_called_once_with(settings, transport_arguments)
    configure_runtime_settings.assert_called_once_with(settings)
    configure_runtime_mode.assert_called_once_with("mcp")
    configure_auth.assert_called_once_with(settings)
    mcp_parser.parse_args.assert_called_once_with(["--stdio"])
    run_from_args.assert_called_once_with(mcp_parser, transport_arguments, settings)


def test_cli_runs_scheduler_with_pydantic_runtime_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch the scheduler while Pydantic Settings owns its runtime flags."""
    import lunchmoney_app.cli as cli

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
            "--schedule-cron",
            "15 4 * * 1-5",
            "--schedule-timezone",
            "America/Denver",
        ]
    )

    parse_cli_settings.assert_called_once_with(
        [
            "--schedule-cron",
            "15 4 * * 1-5",
            "--schedule-timezone",
            "America/Denver",
        ],
        ScheduleCliSettings,
    )
    configure_runtime_settings.assert_called_once_with(settings)
    run_schedule_process.assert_awaited_once_with(settings=settings)


def test_cli_runs_fastapi_with_pydantic_runtime_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass Pydantic Settings CLI flags to the local FastAPI runtime."""
    import lunchmoney_app.cli as cli

    settings = Mock(host="0.0.0.0", port=9000)
    parse_cli_settings = Mock(return_value=settings)
    configure_runtime_settings = Mock()
    export_runtime_settings = Mock()
    run = Mock()
    monkeypatch.setattr(cli, "parse_cli_settings", parse_cli_settings)
    monkeypatch.setattr(cli, "configure_runtime_settings", configure_runtime_settings)
    monkeypatch.setattr(cli, "export_runtime_settings", export_runtime_settings)
    monkeypatch.setattr(cli.uvicorn, "run", run)

    cli.main(["serve", "--host", "0.0.0.0", "--port", "9000"])

    parse_cli_settings.assert_called_once_with(
        ["--host", "0.0.0.0", "--port", "9000"],
        ServeCliSettings,
    )
    configure_runtime_settings.assert_called_once_with(settings)
    export_runtime_settings.assert_called_once_with(settings)
    run.assert_called_once_with(
        "lunchmoney_app.app.main:app",
        host="0.0.0.0",
        port=9000,
        reload=True,
        log_config=cli.LOG_CONFIG,
    )


def test_cli_runs_one_foreground_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch one-off sync arguments without exposing secret CLI flags."""
    import lunchmoney_app.cli as cli

    settings = Mock(sync_safety_margin_minutes=7)
    parse_cli_settings = Mock(return_value=settings)
    configure_runtime_settings = Mock()
    configure_runtime_mode = Mock()
    run_sync = AsyncMock()
    monkeypatch.setattr(cli, "parse_cli_settings", parse_cli_settings)
    monkeypatch.setattr(cli, "configure_runtime_settings", configure_runtime_settings)
    monkeypatch.setattr(cli, "configure_runtime_mode", configure_runtime_mode)
    monkeypatch.setattr(cli, "_run_sync", run_sync)

    cli.main(["sync", "--days", "14", "--incremental"])

    parse_cli_settings.assert_called_once_with(
        ["--days", "14", "--incremental"],
        SyncCliSettings,
        root_parser=ANY,
    )
    configure_runtime_settings.assert_called_once_with(settings)
    configure_runtime_mode.assert_called_once_with("sync")
    run_sync.assert_awaited_once_with(
        days=14,
        incremental=True,
        safety_margin_minutes=7,
    )


def test_cli_reports_local_doctor_failure_with_exit_code_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return a meaningful failure when local doctor checks are unhealthy."""
    import lunchmoney_app.cli as cli

    report = Mock(is_healthy=False)
    report.render.return_value = "redacted diagnostic"
    monkeypatch.setattr(cli, "build_doctor_report", Mock(return_value=report))
    monkeypatch.setattr(cli, "parse_cli_settings", Mock(return_value=Mock()))
    monkeypatch.setattr(cli, "get_secret_settings", Mock(return_value=Mock()))

    with pytest.raises(SystemExit, match="1"):
        cli.main(["doctor"])

    assert capsys.readouterr().out == "redacted diagnostic\n"


def test_cli_reports_invalid_doctor_configuration_with_exit_code_two(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject invalid local configuration without rendering its source values."""
    import lunchmoney_app.cli as cli

    monkeypatch.setenv("LUNCHMONEY_ALLOWED_HOSTS", "*")

    with pytest.raises(SystemExit) as error:
        cli.main(["doctor"])

    assert error.value.code == 2
    assert "invalid local configuration" in capsys.readouterr().err


def test_cli_prints_installed_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Print the distribution name and installed version without configuration."""
    import lunchmoney_app.cli as cli

    cli.main(["version"])

    assert capsys.readouterr().out == f"{cli.__application__} {cli.__version__}\n"


def test_cli_prints_requested_shell_completion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Generate the requested completion script without selecting a runtime."""
    import lunchmoney_app.cli as cli

    cli.main(["--print-completion", "bash"])

    completion_script = capsys.readouterr().out
    assert "complete -F _lunchmoney_app lunchmoney-app" in completion_script
    assert "mcp serve schedule sync doctor version" in completion_script


def test_cli_rejects_shell_completion_with_a_runtime_command() -> None:
    """Keep completion generation separate from command execution."""
    import lunchmoney_app.cli as cli

    with pytest.raises(SystemExit) as error:
        cli.main(["--print-completion", "zsh", "mcp"])

    assert error.value.code == 2
