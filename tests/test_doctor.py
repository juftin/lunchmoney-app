"""Tests for local, redacted command-line diagnostics."""

from pathlib import Path

from lunchmoney_mcp.config import RuntimeSettings, SecretSettings
from lunchmoney_mcp.doctor import build_doctor_report


def test_doctor_reports_missing_access_token_without_leaking_database_secret(
    tmp_path: Path,
) -> None:
    """Require the upstream token while keeping all configured secrets redacted."""
    database_password = "synthetic-database-password"
    report = build_doctor_report(
        settings=RuntimeSettings(),
        secret_settings=SecretSettings(
            access_token="",
            database_url=(
                "postgresql+asyncpg://user:"
                f"{database_password}@database.example/lunchmoney"
            ),
        ),
        config_path=tmp_path / ".env",
    )

    assert report.is_healthy is False
    assert "Lunch Money access token: not configured" in report.render()
    assert "remote database configured; connection is not attempted" in report.render()
    assert database_password not in report.render()


def test_doctor_checks_local_sqlite_directory_without_opening_the_database(
    tmp_path: Path,
) -> None:
    """Accept a writable SQLite parent directory as a local prerequisite."""
    config_path = tmp_path / ".env"
    config_path.touch()
    report = build_doctor_report(
        settings=RuntimeSettings(),
        secret_settings=SecretSettings(
            access_token="synthetic-access-token",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'lunchmoney.db'}",
        ),
        config_path=config_path,
    )

    assert report.is_healthy is True
    assert "configuration file: " in report.render()
    assert "SQLite data directory is writable" in report.render()
    assert "synthetic-access-token" not in report.render()
