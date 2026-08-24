"""Alembic environment for asynchronous SQLite and PostgreSQL migrations."""

import asyncio
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from lunchmoney_app.database.backend import resolve_database_url
from lunchmoney_app.database.models import (  # noqa: F401
    CachedApiResponse,
    RecurringItem,
    Category,
    ManualAccount,
    PlaidAccount,
    ScheduledSyncRun,
    SyncMetadata,
    Tag,
    Transaction,
    TransactionAttachment,
    TransactionTagLink,
    User,
)

config = context.config
"""Alembic configuration supplied by the command entry point."""

if config.config_file_name is not None and not logging.getLogger().handlers:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata
"""Complete registered SQLModel metadata used by Alembic autogeneration."""


def _database_configuration() -> dict[str, str]:
    """Return engine settings with backend-compatible URL precedence."""
    configuration = config.get_section(config.config_ini_section) or {}
    configured_url = configuration.get("sqlalchemy.url") or None
    configuration["sqlalchemy.url"] = resolve_database_url(configured_url)
    return configuration


def run_migrations_offline() -> None:
    """Run migrations without creating an Engine."""
    context.configure(
        url=_database_configuration()["sqlalchemy.url"],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure and run migrations on a synchronous connection adapter."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using Alembic's asynchronous engine template."""
    connectable = async_engine_from_config(
        _database_configuration(),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Enter the asynchronous migration runner from Alembic's sync API."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, run_async_migrations())
            future.result()
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
