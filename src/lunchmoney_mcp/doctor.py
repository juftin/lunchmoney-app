"""Local, redacted operator diagnostics for the command-line interface."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lunchmoney_mcp.config import RuntimeSettings, SecretSettings

DoctorStatus = Literal["ok", "warning", "error"]
"""Severity assigned to one local diagnostic result."""


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """One redacted local diagnostic result.

    Attributes
    ----------
    name : str
        Stable name of the checked local concern.
    status : DoctorStatus
        Result severity used to determine the process exit code.
    detail : str
        Human-readable result that never contains a secret value.
    """

    name: str
    status: DoctorStatus
    detail: str


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Collection of local diagnostics rendered by the ``doctor`` command."""

    checks: tuple[DoctorCheck, ...]
    """Completed local checks in presentation order."""

    @property
    def is_healthy(self) -> bool:
        """Return whether no required local prerequisite is missing."""
        return all(check.status != "error" for check in self.checks)

    def render(self) -> str:
        """Render a stable, human-readable, secret-free diagnostic report."""
        lines = ["Lunch Money MCP local diagnostics"]
        lines.extend(
            f"{check.status.upper():7} {check.name}: {check.detail}"
            for check in self.checks
        )
        lines.append(
            "Result: healthy" if self.is_healthy else "Result: action required"
        )
        return "\n".join(lines)


def build_doctor_report(
    settings: RuntimeSettings,
    secret_settings: SecretSettings,
    config_path: Path = Path(".env"),
) -> DoctorReport:
    """Inspect local configuration without contacting Lunch Money or Redis.

    Parameters
    ----------
    settings : RuntimeSettings
        Resolved non-secret runtime configuration.
    secret_settings : SecretSettings
        Resolved environment and dotenv credentials, inspected only for presence.
    config_path : Path
        Dotenv file location reported to the operator.

    Returns
    -------
    DoctorReport
        Redacted configuration and local filesystem diagnostics.
    """
    access_token_check = DoctorCheck(
        name="Lunch Money access token",
        status="ok" if secret_settings.access_token else "error",
        detail="configured" if secret_settings.access_token else "not configured",
    )
    config_file_check = DoctorCheck(
        name="configuration file",
        status="ok" if config_path.is_file() else "warning",
        detail=f"{config_path} found"
        if config_path.is_file()
        else f"{config_path} not found; environment values remain supported",
    )
    database_check = _database_check(
        database_url=secret_settings.database_url,
        stateless=settings.stateless,
    )
    redis_check = DoctorCheck(
        name="Redis lock backend",
        status="ok",
        detail="configured"
        if secret_settings.redis_url
        else "not configured; file locks will be used",
    )
    api_key_check = DoctorCheck(
        name="REST API authentication",
        status="ok" if secret_settings.mcp_api_key else "warning",
        detail="configured"
        if secret_settings.mcp_api_key
        else "not configured; local REST API requests are unauthenticated",
    )
    return DoctorReport(
        checks=(
            access_token_check,
            config_file_check,
            database_check,
            redis_check,
            api_key_check,
        )
    )


def _database_check(database_url: str, stateless: bool) -> DoctorCheck:
    """Check only the local SQLite data directory, never a remote database."""
    if stateless:
        return DoctorCheck(
            name="database",
            status="ok",
            detail="stateless in-memory SQLite selected",
        )
    if not database_url.startswith("sqlite"):
        return DoctorCheck(
            name="database",
            status="ok",
            detail="remote database configured; connection is not attempted",
        )
    database_path = database_url.partition(":///")[2]
    if (
        not database_path
        or database_path.startswith("file:")
        or database_path == ":memory:"
    ):
        return DoctorCheck(
            name="database",
            status="ok",
            detail="in-memory SQLite configured",
        )
    directory = Path(database_path).expanduser().parent
    if directory.is_dir() and os.access(directory, os.W_OK):
        return DoctorCheck(
            name="database",
            status="ok",
            detail="SQLite data directory is writable",
        )
    return DoctorCheck(
        name="database",
        status="error",
        detail="SQLite data directory is not writable",
    )


__all__ = ["DoctorCheck", "DoctorReport", "DoctorStatus", "build_doctor_report"]
