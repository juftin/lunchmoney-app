"""Add incremental synchronization watermark metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
"""Unique identifier for the synchronization metadata revision."""
down_revision: str | None = "0001"
"""Initial schema revision extended by this migration."""
branch_labels: str | Sequence[str] | None = None
"""This revision does not start a named branch."""
depends_on: str | Sequence[str] | None = None
"""This revision has no external revision dependency."""


def upgrade() -> None:
    """Create the per-domain synchronization watermark table."""
    op.create_table(
        "sync_metadata",
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("domain"),
    )


def downgrade() -> None:
    """Drop the per-domain synchronization watermark table."""
    op.drop_table("sync_metadata")
