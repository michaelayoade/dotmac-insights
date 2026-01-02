"""Add foreign key constraints to tickets audit columns

Revision ID: tickets_audit_fks_001
Revises: audit_indexes_001
Create Date: 2026-01-02

The tickets table has audit columns (created_by_id, updated_by_id, deleted_by_id)
but they lack FK constraints to users table, unlike all other high-traffic tables.
This migration adds the missing FK constraints for consistency.
"""
from alembic import op
from sqlalchemy import text


revision = "tickets_audit_fks_001"
down_revision = "audit_indexes_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Add FK constraints to tickets audit columns (columns already exist)
    # Use IF NOT EXISTS pattern via raw SQL for safety

    # First check if constraints exist
    result = conn.execute(text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'tickets'
        AND constraint_type = 'FOREIGN KEY'
        AND constraint_name IN (
            'fk_tickets_created_by_id_users',
            'fk_tickets_updated_by_id_users',
            'fk_tickets_deleted_by_id_users'
        )
    """))
    existing_constraints = {row[0] for row in result}

    # Add missing FK constraints
    if 'fk_tickets_created_by_id_users' not in existing_constraints:
        conn.execute(text("""
            ALTER TABLE tickets
            ADD CONSTRAINT fk_tickets_created_by_id_users
            FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE SET NULL
        """))

    if 'fk_tickets_updated_by_id_users' not in existing_constraints:
        conn.execute(text("""
            ALTER TABLE tickets
            ADD CONSTRAINT fk_tickets_updated_by_id_users
            FOREIGN KEY (updated_by_id) REFERENCES users(id) ON DELETE SET NULL
        """))

    if 'fk_tickets_deleted_by_id_users' not in existing_constraints:
        conn.execute(text("""
            ALTER TABLE tickets
            ADD CONSTRAINT fk_tickets_deleted_by_id_users
            FOREIGN KEY (deleted_by_id) REFERENCES users(id) ON DELETE SET NULL
        """))


def downgrade() -> None:
    conn = op.get_bind()

    # Drop FK constraints
    conn.execute(text("ALTER TABLE tickets DROP CONSTRAINT IF EXISTS fk_tickets_created_by_id_users"))
    conn.execute(text("ALTER TABLE tickets DROP CONSTRAINT IF EXISTS fk_tickets_updated_by_id_users"))
    conn.execute(text("ALTER TABLE tickets DROP CONSTRAINT IF EXISTS fk_tickets_deleted_by_id_users"))
