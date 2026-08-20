"""Add payload storage to synchronization metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
"""Unique identifier for the synchronization metadata payload revision."""
down_revision: str | None = "0005"
"""Recurring-item persistence revision extended by this migration."""
branch_labels: str | Sequence[str] | None = None
"""This revision does not start a named branch."""
depends_on: str | Sequence[str] | None = None
"""This revision has no external revision dependency."""


def upgrade() -> None:
    """Add optional serialized metadata to synchronization watermarks."""
    op.add_column(
        "sync_metadata",
        sa.Column("payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove optional synchronization metadata payload storage."""
    op.drop_column("sync_metadata", "payload")
