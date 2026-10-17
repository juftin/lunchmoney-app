"""Regression tests for transaction identifiers beyond signed 32-bit integers."""

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from lunchmoney.models import TransactionObject
from sqlalchemy import BigInteger, Integer, inspect
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, col, delete, select

from lunchmoney_app.database import LunchMoneyDatabase
from lunchmoney_app.database.models import Tag, Transaction
from factories import (
    child_transaction_object,
    tag_object,
    transaction_attachment_object,
    transaction_object,
)

TRANSACTION_ID_COLUMNS = (
    ("transactions", "id"),
    ("transactions", "split_parent_id"),
    ("transactions", "group_parent_id"),
    ("transaction_tag_links", "transaction_id"),
    ("transaction_attachments", "transaction_id"),
)
"""Every stored identifier or reference that carries a transaction ID."""

LARGE_TRANSACTION_ID = 3_000_000_000
"""Synthetic identifier exceeding PostgreSQL's signed INTEGER maximum."""


@pytest.mark.parametrize(("table_name", "column_name"), TRANSACTION_ID_COLUMNS)
def test_transaction_ids_use_bigint_postgres_bindings(
    table_name: str,
    column_name: str,
) -> None:
    """Bind transaction keys and references as BIGINT while retaining SQLite INTEGER."""
    column = SQLModel.metadata.tables[table_name].c[column_name]
    statement = select(column).where(column.in_([LARGE_TRANSACTION_ID]))

    compiled = statement.compile(
        dialect=postgresql.asyncpg.dialect(),
        compile_kwargs={"render_postcompile": True},
    )

    assert "$1::BIGINT" in str(compiled)
    assert list(compiled.params.values()) == [LARGE_TRANSACTION_ID]
    assert isinstance(column.type.dialect_impl(postgresql.dialect()), BigInteger)
    assert type(column.type.dialect_impl(sqlite.dialect())) is Integer


def _transaction_graph(transaction_id: int) -> TransactionObject:
    """Build a synthetic graph exercising both parent references and owned tables."""
    children = [
        child_transaction_object(
            transaction_id=transaction_id + offset,
            split_parent_id=None if grouped else transaction_id,
            group_parent_id=transaction_id if grouped else None,
            tag_ids=[21],
            files=[transaction_attachment_object(attachment_id=501 + offset)],
        ).model_copy(update={"category_id": None, "manual_account_id": None})
        for offset, grouped in ((1, False), (2, True))
    ]
    return transaction_object(
        transaction_id=transaction_id,
        children=children,
        is_group_parent=True,
        tag_ids=[21],
        files=[transaction_attachment_object()],
    ).model_copy(update={"category_id": None, "plaid_account_id": None})


async def _clear_transactions(database_url: str) -> None:
    """Remove large IDs before the PostgreSQL downgrade restores 32-bit storage."""
    async with LunchMoneyDatabase(database_url) as database:
        async with database.session_factory() as session, session.begin():
            await session.exec(delete(Transaction))


@pytest.fixture(params=("sqlite", "postgres"))
def previous_revision_database(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> Iterator[tuple[str, Config]]:
    """Provide a revision-0006 database and always remove the test schema."""
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'transaction-ids.db'}"
    if request.param == "postgres":
        postgres_url = os.getenv("TEST_POSTGRES_URL")
        if not postgres_url:
            pytest.skip("TEST_POSTGRES_URL is not configured")
        database_url = postgres_url
    project_root = Path(__file__).parents[2]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option(
        "script_location", str(project_root / "src/lunchmoney_app/database/migrations")
    )
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "0006")
    try:
        yield database_url, config
    finally:
        asyncio.run(_clear_transactions(database_url))
        command.downgrade(config, "base")


async def _seed_existing_graph(database_url: str) -> None:
    """Persist an existing 32-bit graph using the schema deployed before the fix."""
    async with LunchMoneyDatabase(database_url) as database:
        await database.upsert_many(
            [
                Tag.from_api(tag_object(tag_id=21)),
                Transaction.from_api(_transaction_graph(100)),
            ]
        )


async def _verify_upgraded_graphs(database_url: str) -> None:
    """Verify migrated column widths, preserved graphs, and large-ID sync updates."""
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            for table_name, column_name in TRANSACTION_ID_COLUMNS:
                columns = await connection.run_sync(
                    lambda sync, table_name=table_name: inspect(sync).get_columns(
                        table_name
                    )
                )
                column = next(item for item in columns if item["name"] == column_name)
                expected_type = (
                    BigInteger if engine.dialect.name == "postgresql" else Integer
                )
                assert isinstance(column["type"], expected_type)
    finally:
        await engine.dispose()

    async with LunchMoneyDatabase(database_url) as database:
        existing = await database.get(Transaction, 100)
        assert existing is not None
        assert existing.to_api().model_dump(mode="json") == _transaction_graph(
            100
        ).model_dump(mode="json")
        api_transaction = _transaction_graph(LARGE_TRANSACTION_ID)
        for payee in ("Synthetic Large-ID Payee", "Updated Synthetic Large-ID Payee"):
            api_transaction = api_transaction.model_copy(update={"payee": payee})
            await database.reconcile_sync_projection(
                records=[Transaction.from_api(api_transaction)],
                authoritative_ids={},
            )
            stored = await database.get(Transaction, LARGE_TRANSACTION_ID)
            assert stored is not None
            assert stored.to_api().model_dump(
                mode="json"
            ) == api_transaction.model_dump(mode="json")
        async with database.session_factory() as session:
            stored_ids = (
                await session.exec(
                    select(Transaction.id).where(
                        col(Transaction.id) >= LARGE_TRANSACTION_ID
                    )
                )
            ).all()
        assert set(stored_ids) == {LARGE_TRANSACTION_ID + offset for offset in range(3)}


def test_transaction_id_migration_preserves_graphs_and_supports_large_sync_ids(
    previous_revision_database: tuple[str, Config],
) -> None:
    """Upgrade populated databases and reconcile complete graphs beyond int32."""
    database_url, config = previous_revision_database
    asyncio.run(_seed_existing_graph(database_url))

    command.upgrade(config, "head")

    asyncio.run(_verify_upgraded_graphs(database_url))
