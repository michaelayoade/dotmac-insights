"""add_erpnext_lead_customer_fk

Revision ID: 20251218_lead_customer_fk
Revises: 20251218_add_bank_acct_fk
Create Date: 2025-12-18

Adds customer_id FK column to erpnext_leads for conversion tracking.
Uses NOT VALID pattern - constraint is added but not validated until separate migration.

Note: Backfill requires matching logic based on lead conversion data (email, phone, or
explicit customer reference). This is done via customer string column if present.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251218_lead_customer_fk"
down_revision: Union[str, None] = "20251218_add_bank_acct_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add customer_id FK column to erpnext_leads with backfill."""
    # Add column
    op.add_column(
        "erpnext_leads",
        sa.Column("customer_id", sa.Integer(), nullable=True),
    )

    # Backfill from existing customer string column (if exists) or email match
    # First try customer column match
    op.execute("""
        UPDATE erpnext_leads el
        SET customer_id = c.id
        FROM customers c
        WHERE el.customer_id IS NULL
          AND el.customer IS NOT NULL
          AND el.customer != ''
          AND (el.customer = c.name OR el.customer = c.erpnext_id)
    """)

    # Then try email match for converted leads without explicit customer reference
    op.execute("""
        UPDATE erpnext_leads el
        SET customer_id = c.id
        FROM customers c
        WHERE el.customer_id IS NULL
          AND el.status = 'Converted'
          AND el.email IS NOT NULL
          AND el.email != ''
          AND LOWER(el.email) = LOWER(c.email)
    """)

    # Add index CONCURRENTLY
    with op.get_context().autocommit_block():
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_erpnext_leads_customer_id
            ON erpnext_leads (customer_id)
        """)

    # Add FK constraint as NOT VALID (instant, no table scan)
    op.execute("""
        ALTER TABLE erpnext_leads
        ADD CONSTRAINT erpnext_leads_customer_id_fkey
        FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON DELETE SET NULL
        NOT VALID
    """)


def downgrade() -> None:
    """Remove customer_id FK column."""
    op.drop_constraint(
        "erpnext_leads_customer_id_fkey",
        "erpnext_leads",
        type_="foreignkey",
    )
    op.drop_index("ix_erpnext_leads_customer_id", "erpnext_leads")
    op.drop_column("erpnext_leads", "customer_id")
