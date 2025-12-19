"""add_supplier_fk

Revision ID: 20251218_add_supplier_fk
Revises: 20251218_fix_svc_token_fk
Create Date: 2025-12-18

Adds supplier_id FK column to purchase_invoices with backfill from supplier string.
Uses NOT VALID pattern - constraint is added but not validated until separate migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251218_add_supplier_fk"
down_revision: Union[str, None] = "20251218_fix_svc_token_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add supplier_id FK column to purchase_invoices with backfill."""
    # Add column
    op.add_column(
        "purchase_invoices",
        sa.Column("supplier_id", sa.Integer(), nullable=True),
    )

    # Backfill from existing supplier string column
    # Match on supplier name or erpnext_id
    op.execute("""
        UPDATE purchase_invoices pi
        SET supplier_id = s.id
        FROM suppliers s
        WHERE pi.supplier_id IS NULL
          AND pi.supplier IS NOT NULL
          AND pi.supplier != ''
          AND (pi.supplier = s.name OR pi.supplier = s.erpnext_id)
    """)

    # Add index CONCURRENTLY
    with op.get_context().autocommit_block():
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_purchase_invoices_supplier_id
            ON purchase_invoices (supplier_id)
        """)

    # Add FK constraint as NOT VALID (instant, no table scan)
    op.execute("""
        ALTER TABLE purchase_invoices
        ADD CONSTRAINT purchase_invoices_supplier_id_fkey
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        ON DELETE SET NULL
        NOT VALID
    """)


def downgrade() -> None:
    """Remove supplier_id FK column."""
    op.drop_constraint(
        "purchase_invoices_supplier_id_fkey",
        "purchase_invoices",
        type_="foreignkey",
    )
    op.drop_index("ix_purchase_invoices_supplier_id", "purchase_invoices")
    op.drop_column("purchase_invoices", "supplier_id")
