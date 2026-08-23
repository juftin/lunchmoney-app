"""Create the complete initial Lunch Money persistence schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
"""Unique identifier for the initial schema revision."""
down_revision: str | None = None
"""Initial revisions have no predecessor."""
branch_labels: str | Sequence[str] | None = None
"""This revision does not start a named branch."""
depends_on: str | Sequence[str] | None = None
"""This revision has no external revision dependency."""


def upgrade() -> None:
    """Create all current SQLModel tables, constraints, and indexes."""
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_income", sa.Boolean(), nullable=False),
        sa.Column("exclude_from_budget", sa.Boolean(), nullable=False),
        sa.Column("exclude_from_totals", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("is_group", sa.Boolean(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=True),
        sa.Column("collapsed", sa.Boolean(), nullable=True),
        sa.Column("children_present", sa.Boolean(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["categories.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_categories_id", "categories", ["id"], unique=False)

    op.create_table(
        "manual_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("institution_name", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("subtype", sa.String(), nullable=True),
        sa.Column("balance", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("to_base", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("balance_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("balance_as_of_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("closed_on", sa.Date(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("custom_metadata", sa.JSON(), nullable=True),
        sa.Column("exclude_from_transactions", sa.Boolean(), nullable=False),
        sa.Column("created_by_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_offset_minutes", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_manual_accounts_id", "manual_accounts", ["id"], unique=False)

    op.create_table(
        "plaid_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plaid_item_id", sa.String(), nullable=True),
        sa.Column("date_linked", sa.Date(), nullable=False),
        sa.Column("linked_by_name", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("subtype", sa.String(), nullable=False),
        sa.Column("mask", sa.String(), nullable=False),
        sa.Column("institution_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("allow_transaction_modifications", sa.Boolean(), nullable=False),
        sa.Column("limit", sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column("balance", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("to_base", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("balance_last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("balance_last_update_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("import_start_date", sa.Date(), nullable=True),
        sa.Column("last_import", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_import_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("last_fetch", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fetch_offset_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "plaid_last_successful_update",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "plaid_last_successful_update_offset_minutes",
            sa.Integer(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plaid_accounts_id", "plaid_accounts", ["id"], unique=False)

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("text_color", sa.String(), nullable=True),
        sa.Column("background_color", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at_offset_minutes", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tags_id", "tags", ["id"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("budget_name", sa.String(), nullable=False),
        sa.Column("primary_currency", sa.String(), nullable=False),
        sa.Column("api_key_label", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("var_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("to_base", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("recurring_id", sa.Integer(), nullable=True),
        sa.Column("payee", sa.String(), nullable=False),
        sa.Column("original_name", sa.String(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("plaid_account_id", sa.Integer(), nullable=True),
        sa.Column("manual_account_id", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("is_pending", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("is_split_parent", sa.Boolean(), nullable=True),
        sa.Column("split_parent_id", sa.Integer(), nullable=True),
        sa.Column("is_group_parent", sa.Boolean(), nullable=False),
        sa.Column("group_parent_id", sa.Integer(), nullable=True),
        sa.Column("plaid_metadata", sa.JSON(), nullable=True),
        sa.Column("plaid_metadata_present", sa.Boolean(), nullable=False),
        sa.Column("custom_metadata", sa.JSON(), nullable=True),
        sa.Column("custom_metadata_present", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("child_position", sa.Integer(), nullable=True),
        sa.Column("children_present", sa.Boolean(), nullable=False),
        sa.Column("files_present", sa.Boolean(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["plaid_account_id"], ["plaid_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["manual_account_id"], ["manual_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["split_parent_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["group_parent_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_id", "transactions", ["id"], unique=False)

    op.create_table(
        "transaction_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("api_id", sa.Integer(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at_offset_minutes", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transaction_attachments_api_id",
        "transaction_attachments",
        ["api_id"],
        unique=False,
    )

    op.create_table(
        "transaction_tag_links",
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("transaction_id", "tag_id"),
    )


def downgrade() -> None:
    """Drop every application table in reverse dependency order."""
    op.drop_table("transaction_tag_links")
    op.drop_index(
        "ix_transaction_attachments_api_id",
        table_name="transaction_attachments",
    )
    op.drop_table("transaction_attachments")
    op.drop_index("ix_transactions_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_tags_id", table_name="tags")
    op.drop_table("tags")
    op.drop_index("ix_plaid_accounts_id", table_name="plaid_accounts")
    op.drop_table("plaid_accounts")
    op.drop_index("ix_manual_accounts_id", table_name="manual_accounts")
    op.drop_table("manual_accounts")
    op.drop_index("ix_categories_id", table_name="categories")
    op.drop_table("categories")
