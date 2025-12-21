"""Add indexes for contacts filters and expense claims sorting.

Revision ID: 20251220_add_contact_and_expense_indexes
Revises: 20251220_add_contact_lists
Create Date: 2025-12-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251220_add_contact_and_expense_indexes"
down_revision: Union[str, Sequence[str]] = "20251220_add_contact_lists"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create supporting indexes for common queries."""
    op.create_index(
        "ix_unified_contacts_tags_gin",
        "unified_contacts",
        ["tags"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_unified_contacts_lead_qualification",
        "unified_contacts",
        ["lead_qualification"],
        unique=False,
    )
    op.create_index(
        "ix_unified_contacts_outstanding_balance_positive",
        "unified_contacts",
        ["outstanding_balance"],
        unique=False,
        postgresql_where=sa.text("outstanding_balance > 0"),
    )
    op.create_index(
        "ix_expense_claims_status_created_at",
        "expense_claims",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_expense_claims_created_at",
        "expense_claims",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop supporting indexes."""
    op.drop_index(
        "ix_expense_claims_status_created_at",
        table_name="expense_claims",
    )
    op.drop_index(
        "ix_expense_claims_created_at",
        table_name="expense_claims",
    )
    op.drop_index(
        "ix_unified_contacts_outstanding_balance_positive",
        table_name="unified_contacts",
        postgresql_where=sa.text("outstanding_balance > 0"),
    )
    op.drop_index(
        "ix_unified_contacts_lead_qualification",
        table_name="unified_contacts",
    )
    op.drop_index(
        "ix_unified_contacts_tags_gin",
        table_name="unified_contacts",
        postgresql_using="gin",
    )
