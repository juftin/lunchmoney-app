"""Add recurring-item persistence."""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create recurring-item response storage."""
    op.create_table(
        "recurring_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recurring_items_id", "recurring_items", ["id"])


def downgrade() -> None:
    """Remove recurring-item response storage."""
    op.drop_index("ix_recurring_items_id", table_name="recurring_items")
    op.drop_table("recurring_items")
