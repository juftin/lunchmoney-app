"""Add cached API response snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create response storage for non-relational upstream GETs."""
    op.create_table(
        "cached_api_responses",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    """Remove non-relational upstream response storage."""
    op.drop_table("cached_api_responses")
