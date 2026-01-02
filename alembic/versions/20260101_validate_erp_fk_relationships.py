"""Validate FK constraints added in previous migration.

Run VALIDATE CONSTRAINT separately to avoid blocking during validation.

Revision ID: 20260101_validate_erp_fks
Revises: 20260101_erp_fks
Create Date: 2026-01-01

"""
from alembic import op

# revision identifiers
revision = '20260101_validate_erp_fks'
down_revision = '20260101_erp_fks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Validate constraints (this will lock the table but ensures data integrity)
    op.execute("ALTER TABLE gl_entries VALIDATE CONSTRAINT fk_gl_entries_account_id")
    op.execute("ALTER TABLE gl_entries VALIDATE CONSTRAINT fk_gl_entries_cost_center_id")
    op.execute("ALTER TABLE bank_accounts VALIDATE CONSTRAINT fk_bank_accounts_account_id")


def downgrade() -> None:
    # Nothing to downgrade - constraint validation is idempotent
    pass
