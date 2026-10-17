"""Widen PostgreSQL transaction identifiers beyond the signed 32-bit range."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
"""Unique identifier for the transaction identifier width revision."""
down_revision: str | None = "0006"
"""Synchronization metadata payload revision extended by this migration."""
branch_labels: str | Sequence[str] | None = None
"""This revision does not start a named branch."""
depends_on: str | Sequence[str] | None = None
"""This revision has no external revision dependency."""

TRANSACTION_ID_COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("transactions", "id", False),
    ("transactions", "split_parent_id", True),
    ("transactions", "group_parent_id", True),
    ("transaction_tag_links", "transaction_id", False),
    ("transaction_attachments", "transaction_id", False),
)
"""Transaction keys and references with their existing nullability."""


def upgrade() -> None:
    """Widen transaction keys and references while preserving existing graphs.

    Notes
    -----
    SQLite INTEGER already stores signed 64-bit values, so it needs no DDL.
    PostgreSQL retains the existing indexes and foreign-key delete actions.
    """
    if op.get_context().dialect.name != "postgresql":
        return
    for table_name, column_name, nullable in TRANSACTION_ID_COLUMNS:
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=nullable,
        )


def downgrade() -> None:
    """Restore 32-bit PostgreSQL IDs, failing if stored IDs exceed that range."""
    if op.get_context().dialect.name != "postgresql":
        return
    for table_name, column_name, nullable in reversed(TRANSACTION_ID_COLUMNS):
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=nullable,
        )
