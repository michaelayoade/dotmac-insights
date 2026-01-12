"""Add lowercase project enum values to match Python models.

Revision ID: 20260308_add_project_enum_case
Revises: z3a4b5c6d7e8
Create Date: 2026-03-08

PostgreSQL enums for projectstatus/projectpriority were created with uppercase
values, while Python enums use lowercase. This migration adds lowercase values
so inserts/filters using Python enums work correctly.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260308_add_project_enum_case"
down_revision = "z3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing lowercase enum values for projects."""
    # ProjectStatus enum - add lowercase values
    op.execute("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'open'")
    op.execute("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'completed'")
    op.execute("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'cancelled'")
    op.execute("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'on_hold'")

    # ProjectPriority enum - add lowercase values
    op.execute("ALTER TYPE projectpriority ADD VALUE IF NOT EXISTS 'low'")
    op.execute("ALTER TYPE projectpriority ADD VALUE IF NOT EXISTS 'medium'")
    op.execute("ALTER TYPE projectpriority ADD VALUE IF NOT EXISTS 'high'")


def downgrade() -> None:
    """Cannot remove enum values in PostgreSQL, so this is a no-op."""
    pass
