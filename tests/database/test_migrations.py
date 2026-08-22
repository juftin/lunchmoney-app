"""Integration contract tests for deployable Alembic database migrations."""

import asyncio
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Integer, MetaData, String, UniqueConstraint, inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from lunchmoney_app.database.models import (  # noqa: F401
    Category,
    ManualAccount,
    PlaidAccount,
    SyncMetadata,
    Tag,
    Transaction,
    TransactionAttachment,
    TransactionTagLink,
    User,
)

PROJECT_ROOT = Path(__file__).parents[2]
"""Repository root containing the Alembic configuration under test."""


@pytest.fixture(params=("sqlite", "postgres"), ids=("sqlite", "postgres"))
def migration_database_url(request: pytest.FixtureRequest, tmp_path: Path) -> str:
    """Provide each configured migration backend, skipping absent PostgreSQL."""
    if request.param == "sqlite":
        return f"sqlite+aiosqlite:///{tmp_path / 'migration.db'}"
    postgres_url = os.getenv("TEST_POSTGRES_URL")
    if not postgres_url:
        pytest.skip("TEST_POSTGRES_URL is not configured")
    return postgres_url


def _migration_config(database_url: str | None = None) -> Config:
    """Build a repository Alembic configuration with an optional explicit URL."""
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _type_contract(column_type: Any) -> tuple[str, int | None, int | None]:
    """Reduce a SQL type to its portable affinity and numeric dimensions."""
    affinity = column_type._type_affinity.__name__  # noqa: SLF001
    return (
        affinity,
        getattr(column_type, "precision", None),
        getattr(column_type, "scale", None),
    )


def _metadata_contract(metadata: MetaData) -> dict[str, dict[str, Any]]:
    """Describe every application column, key, foreign key, and index."""
    contract: dict[str, dict[str, Any]] = {}
    for table_name, table in sorted(metadata.tables.items()):
        contract[table_name] = {
            "columns": {
                column.name: {
                    "type": _type_contract(column.type),
                    "nullable": column.nullable,
                    "default": column.server_default is not None,
                }
                for column in table.columns
            },
            "primary_key": tuple(column.name for column in table.primary_key.columns),
            "foreign_keys": {
                (
                    tuple(constraint.column_keys),
                    constraint.referred_table.name,
                    tuple(element.column.name for element in constraint.elements),
                    constraint.ondelete,
                )
                for constraint in table.foreign_key_constraints
            },
            "indexes": {
                (
                    index.name,
                    tuple(column.name for column in index.columns),
                    index.unique,
                )
                for index in table.indexes
            },
            "unique_constraints": {
                tuple(column.name for column in constraint.columns)
                for constraint in table.constraints
                if isinstance(constraint, UniqueConstraint)
            },
        }
    return contract


def _database_default_is_explicit(
    column: Mapping[str, Any],
    primary_key_columns: tuple[str, ...],
) -> bool:
    """Distinguish explicit defaults from generated integer-key sequences."""
    default = column.get("default")
    if default is None:
        return False
    return not (
        column.get("name") in primary_key_columns
        and _type_contract(column["type"])[0] == "Integer"
        and isinstance(default, str)
        and re.fullmatch(r"\s*nextval\s*\(.+\)\s*", default, flags=re.IGNORECASE)
        and (column.get("autoincrement") is True or column.get("identity") is not None)
    )


@pytest.mark.parametrize(
    ("column", "primary_key_columns", "expected"),
    [
        (
            {
                "name": "id",
                "type": Integer(),
                "default": "nextval('users_id_seq'::regclass)",
                "autoincrement": True,
            },
            ("id",),
            False,
        ),
        (
            {
                "name": "id",
                "type": Integer(),
                "default": "nextval('users_id_seq'::regclass)",
                "identity": {"always": False},
            },
            ("id",),
            False,
        ),
        (
            {
                "name": "id",
                "type": Integer(),
                "default": "42",
                "autoincrement": True,
            },
            ("id",),
            True,
        ),
        (
            {
                "name": "name",
                "type": String(),
                "default": "nextval('users_id_seq'::regclass)",
                "autoincrement": True,
            },
            ("name",),
            True,
        ),
    ],
)
def test_database_default_ignores_dialect_generated_autoincrement_default(
    column: Mapping[str, Any],
    primary_key_columns: tuple[str, ...],
    expected: bool,
) -> None:
    """Ignore generated PostgreSQL sequence defaults but retain explicit defaults."""
    assert _database_default_is_explicit(column, primary_key_columns) is expected


def _database_contract(connection: Connection) -> dict[str, dict[str, Any]]:
    """Inspect the migrated schema using the same shape as model metadata."""
    inspector = inspect(connection)
    contract: dict[str, dict[str, Any]] = {}
    application_tables = set(SQLModel.metadata.tables)
    for table_name in sorted(application_tables):
        columns = inspector.get_columns(table_name)
        contract[table_name] = {
            "columns": {
                column["name"]: {
                    "type": _type_contract(column["type"]),
                    "nullable": column["nullable"],
                    "default": _database_default_is_explicit(
                        column,
                        tuple(
                            inspector.get_pk_constraint(table_name)[
                                "constrained_columns"
                            ]
                        ),
                    ),
                }
                for column in columns
            },
            "primary_key": tuple(
                inspector.get_pk_constraint(table_name)["constrained_columns"]
            ),
            "foreign_keys": {
                (
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    tuple(foreign_key["referred_columns"]),
                    _ondelete(foreign_key.get("options", {})),
                )
                for foreign_key in inspector.get_foreign_keys(table_name)
            },
            "indexes": {
                (
                    index["name"],
                    tuple(index["column_names"]),
                    index["unique"],
                )
                for index in inspector.get_indexes(table_name)
            },
            "unique_constraints": {
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints(table_name)
            },
        }
    return contract


def _ondelete(options: Mapping[str, Any]) -> str | None:
    """Return a normalized inspected foreign-key delete action."""
    ondelete = options.get("ondelete")
    return ondelete.upper() if isinstance(ondelete, str) else None


async def _inspect_database(database_url: str) -> dict[str, dict[str, Any]]:
    """Return the application-schema contract through an async connection."""
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_database_contract)
    finally:
        await engine.dispose()


async def _table_names(database_url: str) -> set[str]:
    """Return all table names visible through an async connection."""
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync: inspect(sync).get_table_names()
            )
            return set(table_names)
    finally:
        await engine.dispose()


def _assert_initial_migration_contract(
    config: Config,
    database_url: str,
    metadata: MetaData,
) -> None:
    """Verify a migrated schema matches metadata and always return it to base."""
    command.upgrade(config, "head")
    try:
        table_names = asyncio.run(_table_names(database_url))
        assert set(metadata.tables) <= table_names
        assert asyncio.run(_inspect_database(database_url)) == _metadata_contract(
            metadata
        )
    finally:
        command.downgrade(config, "base")


def test_initial_migration_matches_metadata_and_downgrades(
    migration_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create the complete model schema and remove all application tables."""
    monkeypatch.setenv(
        "LUNCHMONEY_DATABASE_URL",
        "sqlite+aiosqlite:////configured-url-must-take-precedence/invalid.db",
    )
    config = _migration_config(migration_database_url)

    _assert_initial_migration_contract(
        config=config,
        database_url=migration_database_url,
        metadata=SQLModel.metadata,
    )

    remaining_tables = asyncio.run(_table_names(migration_database_url))
    assert set(SQLModel.metadata.tables).isdisjoint(remaining_tables)


def test_head_migration_creates_sync_metadata_table(tmp_path: Path) -> None:
    """Create the incremental-sync watermark table on a fresh database."""
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'sync-metadata.db'}"
    config = _migration_config(database_url)

    command.upgrade(config, "head")
    try:
        assert "sync_metadata" in asyncio.run(_table_names(database_url))
    finally:
        command.downgrade(config, "base")


def test_head_migration_creates_scheduled_sync_runs_table(tmp_path: Path) -> None:
    """Create the persistent scheduler run-reporting table on a fresh database."""
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'scheduled-sync-runs.db'}"
    config = _migration_config(database_url)

    command.upgrade(config, "head")
    try:
        assert "scheduled_sync_runs" in asyncio.run(_table_names(database_url))
    finally:
        command.downgrade(config, "base")


def test_migration_contract_downgrades_after_contract_assertion_failure(
    tmp_path: Path,
) -> None:
    """Reverse an upgraded schema even when the schema contract assertion fails."""
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'failed-contract.db'}"
    config = _migration_config(database_url)

    with pytest.raises(AssertionError):
        _assert_initial_migration_contract(
            config=config,
            database_url=database_url,
            metadata=MetaData(),
        )

    assert set(SQLModel.metadata.tables).isdisjoint(
        asyncio.run(_table_names(database_url))
    )


def test_migration_uses_environment_url_when_config_is_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the backend environment URL when Alembic has no explicit URL."""
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'environment.db'}"
    monkeypatch.setenv("LUNCHMONEY_DATABASE_URL", database_url)
    config = _migration_config()

    command.upgrade(config, "head")
    try:
        assert set(SQLModel.metadata.tables) <= asyncio.run(_table_names(database_url))
    finally:
        command.downgrade(config, "base")
