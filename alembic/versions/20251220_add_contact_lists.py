"""Add contact_lists table for custom contact segments.

Revision ID: 20251220_add_contact_lists
Revises: 20251220_merge_support_heads
Create Date: 2025-12-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20251220_add_contact_lists"
down_revision: Union[str, Sequence[str]] = "20251220_merge_support_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create contact_lists table."""
    op.create_table(
        "contact_lists",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("is_shared", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, default=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_contact_lists_owner_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contact_lists_owner_id", "contact_lists", ["owner_id"], unique=False)
    op.create_index("ix_contact_lists_is_shared", "contact_lists", ["is_shared"], unique=False)
    op.create_index("ix_contact_lists_is_favorite", "contact_lists", ["is_favorite"], unique=False)


def downgrade() -> None:
    """Drop contact_lists table."""
    op.drop_index("ix_contact_lists_is_favorite", table_name="contact_lists")
    op.drop_index("ix_contact_lists_is_shared", table_name="contact_lists")
    op.drop_index("ix_contact_lists_owner_id", table_name="contact_lists")
    op.drop_table("contact_lists")
