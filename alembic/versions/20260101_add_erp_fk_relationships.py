"""Add FK relationships to ERPNext-synced tables.

Links orphan tables to their target master data tables via proper FK columns.

gl_entries.account (text) -> accounts.erpnext_id -> adds gl_entries.account_id -> accounts.id
gl_entries.cost_center (text) -> cost_centers.erpnext_id -> adds gl_entries.cost_center_id -> cost_centers.id
bank_accounts.account (text) -> accounts.erpnext_id -> adds bank_accounts.account_id -> accounts.id

Revision ID: 20260101_erp_fks
Revises: e21011c370d4
Create Date: 2026-01-01

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '20260101_erp_fks'
down_revision = 'e21011c370d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add FK columns (nullable initially for backfill)
    op.add_column('gl_entries', sa.Column('account_id', sa.Integer(), nullable=True))
    op.add_column('gl_entries', sa.Column('cost_center_id', sa.Integer(), nullable=True))
    op.add_column('bank_accounts', sa.Column('account_id', sa.Integer(), nullable=True))

    # Backfill gl_entries.account_id from accounts.erpnext_id
    op.execute("""
        UPDATE gl_entries g
        SET account_id = a.id
        FROM accounts a
        WHERE g.account = a.erpnext_id
        AND g.account_id IS NULL
    """)

    # Backfill gl_entries.cost_center_id from cost_centers.erpnext_id
    op.execute("""
        UPDATE gl_entries g
        SET cost_center_id = c.id
        FROM cost_centers c
        WHERE g.cost_center = c.erpnext_id
        AND g.cost_center_id IS NULL
    """)

    # Backfill bank_accounts.account_id from accounts.erpnext_id
    op.execute("""
        UPDATE bank_accounts b
        SET account_id = a.id
        FROM accounts a
        WHERE b.account = a.erpnext_id
        AND b.account_id IS NULL
    """)

    # Create indexes for FK columns (before adding constraints)
    op.create_index('ix_gl_entries_account_id', 'gl_entries', ['account_id'])
    op.create_index('ix_gl_entries_cost_center_id', 'gl_entries', ['cost_center_id'])
    op.create_index('ix_bank_accounts_account_id', 'bank_accounts', ['account_id'])

    # Add FK constraints (NOT VALID for faster initial creation on large tables)
    op.execute("""
        ALTER TABLE gl_entries
        ADD CONSTRAINT fk_gl_entries_account_id
        FOREIGN KEY (account_id) REFERENCES accounts(id)
        NOT VALID
    """)

    op.execute("""
        ALTER TABLE gl_entries
        ADD CONSTRAINT fk_gl_entries_cost_center_id
        FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id)
        NOT VALID
    """)

    op.execute("""
        ALTER TABLE bank_accounts
        ADD CONSTRAINT fk_bank_accounts_account_id
        FOREIGN KEY (account_id) REFERENCES accounts(id)
        NOT VALID
    """)


def downgrade() -> None:
    # Drop FK constraints
    op.drop_constraint('fk_bank_accounts_account_id', 'bank_accounts', type_='foreignkey')
    op.drop_constraint('fk_gl_entries_cost_center_id', 'gl_entries', type_='foreignkey')
    op.drop_constraint('fk_gl_entries_account_id', 'gl_entries', type_='foreignkey')

    # Drop indexes
    op.drop_index('ix_bank_accounts_account_id', 'bank_accounts')
    op.drop_index('ix_gl_entries_cost_center_id', 'gl_entries')
    op.drop_index('ix_gl_entries_account_id', 'gl_entries')

    # Drop columns
    op.drop_column('bank_accounts', 'account_id')
    op.drop_column('gl_entries', 'cost_center_id')
    op.drop_column('gl_entries', 'account_id')
