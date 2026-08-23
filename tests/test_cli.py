"""Tests for the Click command-line process dispatcher."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture(autouse=True)
def reset_runtime_configuration() -> Iterator[None]:
    """Prevent process-local CLI settings from leaking between tests."""
    import lunchmoney_app.config as config

    yield
    config._runtime_settings = None
    config._runtime_mode = None
    config.get_settings.cache_clear()


def test_cli_runs_standalone_mcp_without_persistent_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch a Click transport flag with Pydantic-resolved settings."""
    import lunchmoney_app.cli as cli

    settings = Mock()
    resolved_settings = Mock()
    resolve_settings = Mock(return_value=settings)
    apply_transport_defaults = Mock(return_value=resolved_settings)
    configure_runtime_settings = Mock()
    configure_runtime_mode = Mock()
    configure_auth = Mock()
    run_from_args = Mock()
    parser = Mock()
    monkeypatch.setattr(cli, "_resolve_settings", resolve_settings)
    monkeypatch.setattr(cli, "configure_runtime_settings", configure_runtime_settings)
    monkeypatch.setattr(cli, "configure_runtime_mode", configure_runtime_mode)
    monkeypatch.setattr(cli.mcp_server, "configure_auth", configure_auth)
    monkeypatch.setattr(
        cli.mcp_server, "apply_transport_defaults", apply_transport_defaults
    )
    monkeypatch.setattr(
        cli.mcp_server, "create_argument_parser", Mock(return_value=parser)
    )
    monkeypatch.setattr(cli.mcp_server, "run_from_args", run_from_args)

    cli.main(["mcp", "--stdio"])

    resolve_settings.assert_called_once()
    arguments = apply_transport_defaults.call_args.args[1]
    assert arguments.transport == "stdio"
    configure_runtime_settings.assert_called_once_with(resolved_settings)
    configure_runtime_mode.assert_called_once_with("mcp")
    configure_auth.assert_called_once_with(resolved_settings)
    run_from_args.assert_called_once_with(parser, arguments, resolved_settings)


@pytest.mark.parametrize(
    "arguments",
    [
        ["mcp", "--stdio", "--sse"],
        ["mcp", "--stdio", "--host", "0.0.0.0"],
    ],
)
def test_cli_rejects_ambiguous_mcp_transport_options(arguments: list[str]) -> None:
    """Reject conflicting transports and stdio-only bind arguments."""
    import lunchmoney_app.cli as cli

    with pytest.raises(SystemExit) as error:
        cli.main(arguments)

    assert error.value.code == 2


def test_cli_runs_scheduler_with_pydantic_runtime_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass Click overrides to the scheduler's Pydantic Settings model."""
    import lunchmoney_app.cli as cli

    settings = Mock()
    resolve_settings = Mock(return_value=settings)
    run_schedule_process = AsyncMock()
    configure_runtime_settings = Mock()
    monkeypatch.setattr(cli, "_resolve_settings", resolve_settings)
    monkeypatch.setattr(cli, "run_schedule_process", run_schedule_process)
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

    values = resolve_settings.call_args.args[2]
    assert values["schedule_cron"] == "15 4 * * 1-5"
    assert values["schedule_timezone"] == "America/Denver"
    configure_runtime_settings.assert_called_once_with(settings)
    run_schedule_process.assert_awaited_once_with(settings=settings)


def test_cli_runs_fastapi_with_pydantic_runtime_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass Click overrides to the local FastAPI runtime."""
    import lunchmoney_app.cli as cli

    settings = Mock(host="0.0.0.0", port=9000)
    resolve_settings = Mock(return_value=settings)
    configure_runtime_settings = Mock()
    export_runtime_settings = Mock()
    run = Mock()
    monkeypatch.setattr(cli, "_resolve_settings", resolve_settings)
    monkeypatch.setattr(cli, "configure_runtime_settings", configure_runtime_settings)
    monkeypatch.setattr(cli, "export_runtime_settings", export_runtime_settings)
    monkeypatch.setattr(cli.uvicorn, "run", run)

    cli.main(["serve", "--host", "0.0.0.0", "--port", "9000"])

    values = resolve_settings.call_args.args[2]
    assert values["host"] == "0.0.0.0"
    assert values["port"] == 9000
    configure_runtime_settings.assert_called_once_with(settings)
    export_runtime_settings.assert_called_once_with(settings)
    run.assert_called_once_with(
        "lunchmoney_app.app.main:app",
        host="0.0.0.0",
        port=9000,
        reload=True,
        log_config=cli.LOG_CONFIG,
    )


def test_cli_runs_one_foreground_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dispatch operation arguments separately from Pydantic settings."""
    import lunchmoney_app.cli as cli

    settings = Mock(sync_safety_margin_minutes=7)
    resolve_settings = Mock(return_value=settings)
    configure_runtime_settings = Mock()
    configure_runtime_mode = Mock()
    run_sync = AsyncMock()
    monkeypatch.setattr(cli, "_resolve_settings", resolve_settings)
    monkeypatch.setattr(cli, "configure_runtime_settings", configure_runtime_settings)
    monkeypatch.setattr(cli, "configure_runtime_mode", configure_runtime_mode)
    monkeypatch.setattr(cli, "_run_sync", run_sync)

    cli.main(["sync", "--days", "14", "--incremental"])

    configure_runtime_settings.assert_called_once_with(settings)
    configure_runtime_mode.assert_called_once_with("sync")
    run_sync.assert_awaited_once_with(
        days=14,
        incremental=True,
        safety_margin_minutes=7,
    )


def test_cli_prefers_flags_then_pydantic_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve CLI-over-environment precedence at the Click handoff."""
    import lunchmoney_app.cli as cli

    monkeypatch.setenv("LUNCHMONEY_PORT", "9000")
    run = Mock()
    monkeypatch.setattr(cli.uvicorn, "run", run)

    cli.main(["serve", "--port", "8080"])

    assert run.call_args.kwargs["port"] == 8080


def test_cli_help_documents_environment_alternatives(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Show Pydantic defaults and environment names in command help."""
    import lunchmoney_app.cli as cli

    cli.main(["serve", "--help"])

    output = capsys.readouterr().out
    assert "--port INTEGER RANGE" in output
    assert "LUNCHMONEY_PORT" in output
    assert "8000" in output
    assert "--access-token" not in output


def test_cli_reports_local_doctor_failure_with_exit_code_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return a meaningful failure when local doctor checks are unhealthy."""
    import lunchmoney_app.cli as cli

    report = Mock(is_healthy=False)
    report.render.return_value = "redacted diagnostic"
    monkeypatch.setattr(cli, "build_doctor_report", Mock(return_value=report))
    monkeypatch.setattr(cli, "RuntimeSettings", Mock(return_value=Mock()))
    monkeypatch.setattr(cli, "get_secret_settings", Mock(return_value=Mock()))

    with pytest.raises(SystemExit, match="1"):
        cli.main(["doctor"])

    assert capsys.readouterr().out == "redacted diagnostic\n"


def test_cli_reports_invalid_doctor_configuration_with_exit_code_two(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject invalid local configuration without rendering source values."""
    import lunchmoney_app.cli as cli

    monkeypatch.setenv("LUNCHMONEY_ALLOWED_HOSTS", "*")

    with pytest.raises(SystemExit) as error:
        cli.main(["doctor"])

    assert error.value.code == 2
    assert "Invalid configuration" in capsys.readouterr().err


def test_cli_prints_installed_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Print the distribution name and installed version."""
    import lunchmoney_app.cli as cli

    cli.main(["version"])

    assert capsys.readouterr().out == f"{cli.__application__} {cli.__version__}\n"


def test_cli_prints_native_shell_completion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Generate Click's native completion script."""
    import lunchmoney_app.cli as cli

    cli.main(["--print-completion", "bash"])

    completion_script = capsys.readouterr().out
    assert "_LUNCHMONEY_APP_COMPLETE=bash_complete" in completion_script
    assert "complete -o nosort" in completion_script


def test_cli_rejects_shell_completion_with_a_runtime_command() -> None:
    """Keep completion generation separate from command execution."""
    import lunchmoney_app.cli as cli

    with pytest.raises(SystemExit) as error:
        cli.main(["--print-completion", "zsh", "mcp"])

    assert error.value.code == 2


def test_config_lists_all_runtime_and_secret_environment_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Make every setting discoverable without exposing secret flags."""
    import lunchmoney_app.cli as cli

    cli.main(["config", "list"])

    output = capsys.readouterr().out
    assert "LUNCHMONEY_PORT" in output
    assert "LUNCHMONEY_ACCESS_TOKEN" in output
    assert "LUNCHMONEY_APP_API_KEY" in output
    assert "[environment only]" in output


def test_config_show_redacts_sensitive_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Show resolved configuration without revealing credentials."""
    import lunchmoney_app.cli as cli

    monkeypatch.setenv("LUNCHMONEY_ACCESS_TOKEN", "synthetic-secret")

    cli.main(["config", "show"])

    output = capsys.readouterr().out
    assert "********" in output
    assert "synthetic-secret" not in output


def test_config_validate_reports_success(capsys: pytest.CaptureFixture[str]) -> None:
    """Validate all Pydantic Settings models without starting a runtime."""
    import lunchmoney_app.cli as cli

    cli.main(["config", "validate"])

    assert capsys.readouterr().out == "Configuration is valid.\n"
