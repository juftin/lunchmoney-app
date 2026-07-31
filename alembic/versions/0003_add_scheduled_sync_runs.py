"""Add scheduled synchronization run reporting."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
"""Unique identifier for the scheduled synchronization run revision."""
down_revision: str | None = "0002"
"""Incremental synchronization metadata revision extended by this migration."""
branch_labels: str | Sequence[str] | None = None
"""This revision does not start a named branch."""
depends_on: str | Sequence[str] | None = None
"""This revision has no external revision dependency."""


def upgrade() -> None:
    """Create persistent operator-facing records for scheduled sync outcomes."""
    op.create_table(
        "scheduled_sync_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("synced", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scheduled_sync_runs_started_at",
        "scheduled_sync_runs",
        ["started_at"],
    )


def downgrade() -> None:
    """Drop persistent scheduled synchronization run records."""
    op.drop_index("ix_scheduled_sync_runs_started_at", table_name="scheduled_sync_runs")
    op.drop_table("scheduled_sync_runs")
