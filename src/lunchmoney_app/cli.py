"""Click command-line interface for application runtimes and configuration."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from collections.abc import Callable
from typing import Any, Literal, TypeVar, cast, get_args, get_origin

import click
import uvicorn
from click.core import ParameterSource
from click.shell_completion import get_completion_class
from pydantic import ValidationError
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url

from lunchmoney_app.__about__ import __application__, __version__
from lunchmoney_app.app.dependencies import get_lunchmoney_app, get_shared_database
from lunchmoney_app.config import (
    McpCliSettings,
    RuntimeSettings,
    ScheduleCliSettings,
    SecretSettings,
    ServeCliSettings,
    SyncCliSettings,
    configure_runtime_mode,
    configure_runtime_settings,
    export_runtime_settings,
    get_secret_settings,
    get_settings,
)
from lunchmoney_app.doctor import build_doctor_report
from lunchmoney_app.database import (
    drop_all_tables,
    resolve_database_url,
    run_migrations,
)
from lunchmoney_app.locks import LockTimeoutError, get_migration_lock
from lunchmoney_app.logging_config import LOG_CONFIG
from lunchmoney_app.mcp import server as mcp_server
from lunchmoney_app.scheduler import run_schedule_process
from lunchmoney_app.services import execute_sync
from lunchmoney_app.services.errors import StatefulModeRequired
from lunchmoney_app.services.operations import StatefulOperationContextFactory

SettingsType = TypeVar("SettingsType", bound=BaseSettings)
"""Concrete Pydantic Settings model resolved for one command."""

CommandCallback = Callable[..., Any]
"""Click callback decorated with settings-derived options."""


def _environment_name(field_name: str, field: FieldInfo) -> str:
    """Return the environment variable used by a settings field."""
    if isinstance(field.validation_alias, str):
        return field.validation_alias
    return f"LUNCHMONEY_{field_name.upper()}"


def _field_click_type(field: FieldInfo) -> click.ParamType[Any]:
    """Map a Pydantic field's primitive type and bounds to a Click type."""
    default = field.default
    annotation = field.annotation
    if get_origin(annotation) is Literal:
        return click.Choice(tuple(str(value) for value in get_args(annotation)))
    if isinstance(default, bool) or annotation is bool:
        return click.BOOL
    minimum: int | float | None = None
    maximum: int | float | None = None
    minimum_open = False
    maximum_open = False
    for constraint in field.metadata:
        if getattr(constraint, "ge", None) is not None:
            minimum = constraint.ge
        if getattr(constraint, "gt", None) is not None:
            minimum = constraint.gt
            minimum_open = True
        if getattr(constraint, "le", None) is not None:
            maximum = constraint.le
        if getattr(constraint, "lt", None) is not None:
            maximum = constraint.lt
            maximum_open = True
    if isinstance(default, int) or annotation is int:
        if minimum is None and maximum is None:
            return click.INT
        return click.IntRange(
            min=cast(int | None, minimum),
            max=cast(int | None, maximum),
            min_open=minimum_open,
            max_open=maximum_open,
        )
    if isinstance(default, float) or annotation is float:
        if minimum is None and maximum is None:
            return click.FLOAT
        return click.FloatRange(
            min=minimum,
            max=maximum,
            min_open=minimum_open,
            max_open=maximum_open,
        )
    return click.STRING


def _settings_options(
    settings_type: type[BaseSettings],
) -> Callable[[CommandCallback], CommandCallback]:
    """Decorate a Click callback with every safe field in a settings model."""

    def decorator(callback: CommandCallback) -> CommandCallback:
        decorated = callback
        for field_name, field in reversed(settings_type.model_fields.items()):
            option_name = field_name.replace("_", "-")
            environment_name = _environment_name(field_name, field)
            description = field.description or field_name.replace("_", " ").capitalize()
            help_text = f"{description}. Environment: {environment_name}."
            if isinstance(field.default, bool):
                show_default = str(field.default).lower()
            elif field.default is not None:
                show_default = str(field.default)
            else:
                show_default = None
            if isinstance(field.default, bool) or field.annotation is bool:
                decorated = click.option(
                    f"--{option_name}/--no-{option_name}",
                    field_name,
                    default=None,
                    help=help_text,
                    show_default=show_default,
                )(decorated)
            else:
                decorated = click.option(
                    f"--{option_name}",
                    field_name,
                    default=None,
                    type=_field_click_type(field),
                    help=help_text,
                    show_default=show_default,
                )(decorated)
        return decorated

    return decorator


def _format_validation_error(error: ValidationError) -> str:
    """Render Pydantic validation failures as concise terminal messages."""
    messages = []
    for item in error.errors(include_url=False):
        location = ".".join(str(part) for part in item["loc"]) or "configuration"
        messages.append(f"{location}: {item['msg']}")
    return "Invalid configuration:\n  " + "\n  ".join(messages)


def _resolve_settings(
    ctx: click.Context,
    settings_type: type[SettingsType],
    values: dict[str, Any],
) -> RuntimeSettings:
    """Resolve explicit Click overrides through Pydantic Settings."""
    overrides = {
        name: value
        for name, value in values.items()
        if ctx.get_parameter_source(name) is ParameterSource.COMMANDLINE
    }
    try:
        command_settings = settings_type(**overrides)
        return RuntimeSettings.model_validate(
            command_settings.model_dump(exclude_unset=True)
        )
    except ValidationError as error:
        raise click.UsageError(_format_validation_error(error), ctx=ctx) from error


def _render_click_completion(shell: str) -> str:
    """Render Click's native completion source for an installed shell."""
    completion_type = get_completion_class(shell)
    if completion_type is None:  # pragma: no cover - guarded by Click Choice
        raise click.ClickException(f"Unsupported shell: {shell}")
    completion = completion_type(
        cli,
        {},
        __application__,
        f"_{__application__.replace('-', '_').upper()}_COMPLETE",
    )
    return completion.source()


@click.group(invoke_without_command=True)
@click.option(
    "--print-completion",
    type=click.Choice(("bash", "zsh", "fish"), case_sensitive=False),
    metavar="SHELL",
    help="Print a shell completion script and exit.",
)
@click.pass_context
def cli(ctx: click.Context, print_completion: str | None) -> None:
    """Run Lunch Money services and operator commands."""
    if print_completion is not None:
        if ctx.invoked_subcommand is not None:
            raise click.UsageError(
                "--print-completion does not accept a runtime command", ctx=ctx
            )
        click.echo(_render_click_completion(print_completion))
        return
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command("mcp")
@click.option(
    "--transport",
    type=click.Choice(("stdio", "sse", "http", "streamable-http")),
    default=None,
    help="MCP transport. The default is stdio with ephemeral data handling.",
)
@click.option("--stdio", is_flag=True, help="Use stdio.")
@click.option("--sse", is_flag=True, help="Use SSE.")
@click.option("--http", is_flag=True, help="Use HTTP.")
@click.option(
    "--streamable-http",
    is_flag=True,
    help="Use Streamable HTTP.",
)
@_settings_options(McpCliSettings)
@click.pass_context
def mcp_command(
    ctx: click.Context,
    transport: str | None,
    stdio: bool,
    sse: bool,
    http: bool,
    streamable_http: bool,
    **values: Any,
) -> None:
    """Run the standalone MCP server."""
    transport_flags = {
        "stdio": stdio,
        "sse": sse,
        "http": http,
        "streamable-http": streamable_http,
    }
    selected_flags = [name for name, selected in transport_flags.items() if selected]
    if len(selected_flags) + (transport is not None) > 1:
        raise click.UsageError("MCP transport options are mutually exclusive.")
    selected_transport = selected_flags[0] if selected_flags else transport or "stdio"
    explicit_bind_options = any(
        ctx.get_parameter_source(name) is ParameterSource.COMMANDLINE
        for name in ("host", "port")
    )
    if selected_transport == "stdio" and explicit_bind_options:
        raise click.UsageError("--host and --port require an HTTP transport.")
    settings = _resolve_settings(ctx, McpCliSettings, values)
    arguments = argparse.Namespace(transport=selected_transport)
    settings = mcp_server.apply_transport_defaults(settings, arguments)
    configure_runtime_settings(settings)
    configure_runtime_mode("mcp")
    mcp_server.configure_auth(settings)
    mcp_server.run_from_args(mcp_server.create_argument_parser(), arguments, settings)


@cli.command("schedule")
@_settings_options(ScheduleCliSettings)
@click.pass_context
def schedule_command(ctx: click.Context, **values: Any) -> None:
    """Run the opt-in synchronization scheduler."""
    settings = _resolve_settings(ctx, ScheduleCliSettings, values)
    configure_runtime_settings(settings)
    if settings.persistence_mode == "ephemeral":
        _exit_stateful_mode_required()
    configure_runtime_mode("schedule")
    asyncio.run(run_schedule_process(settings=settings))


@cli.command("serve")
@_settings_options(ServeCliSettings)
@click.pass_context
def serve_command(ctx: click.Context, **values: Any) -> None:
    """Run the local FastAPI application."""
    settings = _resolve_settings(ctx, ServeCliSettings, values)
    configure_runtime_settings(settings)
    configure_runtime_mode("serve")
    export_runtime_settings(settings)
    uvicorn.run(
        "lunchmoney_app.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_config=LOG_CONFIG,
    )


@cli.command("sync")
@click.option(
    "--days",
    type=click.IntRange(1, 366),
    default=30,
    show_default=True,
    help="Rolling transaction window for the initial synchronization.",
)
@click.option(
    "--incremental/--no-incremental",
    default=False,
    show_default=True,
    help="Resume transaction synchronization from its saved watermark.",
)
@_settings_options(SyncCliSettings)
@click.pass_context
def sync_command(
    ctx: click.Context,
    days: int,
    incremental: bool,
    **values: Any,
) -> None:
    """Run one foreground synchronization."""
    settings = _resolve_settings(ctx, SyncCliSettings, values)
    configure_runtime_settings(settings)
    configure_runtime_mode("sync")
    try:
        asyncio.run(
            _run_sync(
                days=days,
                incremental=incremental,
                safety_margin_minutes=settings.sync_safety_margin_minutes,
            )
        )
    except StatefulModeRequired:
        _exit_stateful_mode_required()


@cli.command("doctor")
def doctor_command() -> None:
    """Check local configuration without external network requests."""
    try:
        settings = RuntimeSettings()
        secrets = get_secret_settings()
    except ValidationError as error:
        raise click.UsageError(_format_validation_error(error)) from error
    report = build_doctor_report(settings=settings, secret_settings=secrets)
    click.echo(report.render())
    if not report.is_healthy:
        raise click.exceptions.Exit(1)


@cli.command("version")
def version_command() -> None:
    """Print the installed package version."""
    click.echo(f"{__application__} {__version__}")


@cli.group("db")
def db_group() -> None:
    """Inspect, migrate, or delete the configured application database."""


def _database_info() -> dict[str, object]:
    """Return safe JSON-serializable details for the configured database."""
    secret_settings = get_secret_settings()
    database_url = resolve_database_url()
    parsed_url = make_url(database_url)
    database_path: str | None = None
    exists: bool | None = None
    if parsed_url.get_backend_name() == "sqlite" and parsed_url.database is not None:
        database_path = str(Path(parsed_url.database).expanduser().resolve())
        exists = Path(database_path).is_file()
    return {
        "database_url": parsed_url.render_as_string(hide_password=True),
        "database_url_is_explicit": secret_settings.database_url_is_explicit,
        "dialect": parsed_url.get_backend_name(),
        "driver": parsed_url.get_driver_name(),
        "path": database_path,
        "exists": exists,
    }


def _with_migration_lock(callback: Callable[[], None]) -> None:
    """Run an exclusive database operation or report a concurrent runtime."""
    try:
        with get_migration_lock():
            callback()
    except LockTimeoutError as error:
        raise click.ClickException(
            "Database operation could not acquire the migration lock."
        ) from error


@db_group.command("info")
def db_info_command() -> None:
    """Print safe configured-database details as JSON."""
    click.echo(json.dumps(_database_info(), sort_keys=True))


@db_group.command("migrate")
def db_migrate_command() -> None:
    """Apply all pending database migrations."""
    database_url = resolve_database_url()
    _with_migration_lock(lambda: asyncio.run(run_migrations(database_url)))
    click.echo("Database migrations applied.")


@db_group.command("delete")
@click.option(
    "--yes",
    is_flag=True,
    help="Confirm dropping every Lunch Money application table.",
)
def db_delete_command(yes: bool) -> None:
    """Drop every Lunch Money application table from the configured database."""
    database_url = resolve_database_url()
    safe_url = make_url(database_url).render_as_string(hide_password=True)
    if not yes and not click.confirm(
        f"Drop every Lunch Money table in {safe_url}?",
        default=False,
    ):
        click.echo("Aborted.")
        return
    _with_migration_lock(lambda: asyncio.run(drop_all_tables(database_url)))
    click.echo("Database tables deleted.")


def _exit_stateful_mode_required() -> None:
    """Exit safely when a CLI operation is unavailable without persistence."""
    error = StatefulModeRequired()
    click.echo(json.dumps(error.as_dict()), err=True)
    raise SystemExit(1)


@cli.group("config")
def config_group() -> None:
    """Inspect and validate configuration and environment alternatives."""


def _configuration_rows() -> list[tuple[str, FieldInfo, bool]]:
    """Return every runtime and secret setting once in display order."""
    rows = [
        (name, field, False) for name, field in RuntimeSettings.model_fields.items()
    ]
    rows.extend(
        (name, field, True)
        for name, field in SecretSettings.model_fields.items()
        if name not in RuntimeSettings.model_fields
    )
    return rows


@config_group.command("list")
def config_list_command() -> None:
    """List every setting, environment variable, and default."""
    click.echo(f"{'SETTING':<32} {'ENVIRONMENT':<46} DEFAULT")
    for name, field, secret in _configuration_rows():
        default = "[environment only]" if secret else str(field.default)
        click.echo(f"{name:<32} {_environment_name(name, field):<46} {default}")


@config_group.command("show")
def config_show_command() -> None:
    """Show resolved configuration with all sensitive values redacted."""
    try:
        runtime = RuntimeSettings()
        secrets = SecretSettings()
    except ValidationError as error:
        raise click.ClickException(_format_validation_error(error)) from error
    values = runtime.model_dump()
    values.update(secrets.model_dump())
    click.echo(f"{'SETTING':<32} {'ENVIRONMENT':<46} VALUE")
    for name, field, secret in _configuration_rows():
        value = (
            "********" if secret and values.get(name) is not None else values.get(name)
        )
        click.echo(f"{name:<32} {_environment_name(name, field):<46} {value}")


@config_group.command("validate")
def config_validate_command() -> None:
    """Validate runtime and secret configuration without starting a service."""
    try:
        RuntimeSettings()
        SecretSettings()
    except ValidationError as error:
        raise click.ClickException(_format_validation_error(error)) from error
    click.echo("Configuration is valid.")


async def _run_sync(
    days: int,
    incremental: bool,
    safety_margin_minutes: int,
) -> None:
    """Execute one stateful sync and print its concise result."""
    settings = get_settings()
    if settings.persistence_mode == "ephemeral":
        raise StatefulModeRequired
    client = get_lunchmoney_app()
    factory = StatefulOperationContextFactory(client, get_shared_database())
    async with factory.operation() as context:
        response = await execute_sync(
            db=context.database,
            client=client,
            days=days,
            incremental=incremental,
            safety_margin_minutes=safety_margin_minutes,
        )
    click.echo(response.model_dump_json())


def main(argv: list[str] | None = None) -> None:
    """Run the Click CLI while preserving console-script exit semantics."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        result = cli.main(
            args=arguments,
            prog_name=__application__,
            standalone_mode=False,
        )
        if isinstance(result, int) and result != 0:
            raise SystemExit(result)
    except click.ClickException as error:
        error.show()
        raise SystemExit(error.exit_code) from error


__all__ = ["cli", "main"]
