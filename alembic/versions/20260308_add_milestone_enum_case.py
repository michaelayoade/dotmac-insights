"""Add uppercase milestone enum values to match incoming data.

Revision ID: 20260308_add_milestone_enum_case
Revises: 20260308_add_project_enum_case
Create Date: 2026-03-08

PostgreSQL milestonestatus enum currently contains lowercase values, but
some code paths send uppercase values (e.g., PLANNED). This migration adds
uppercase variants to avoid enum input errors.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260308_add_milestone_enum_case"
down_revision = "20260308_add_project_enum_case"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing uppercase enum values for milestones."""
    op.execute("ALTER TYPE milestonestatus ADD VALUE IF NOT EXISTS 'PLANNED'")
    op.execute("ALTER TYPE milestonestatus ADD VALUE IF NOT EXISTS 'IN_PROGRESS'")
    op.execute("ALTER TYPE milestonestatus ADD VALUE IF NOT EXISTS 'COMPLETED'")
    op.execute("ALTER TYPE milestonestatus ADD VALUE IF NOT EXISTS 'ON_HOLD'")


def downgrade() -> None:
    """Cannot remove enum values in PostgreSQL, so this is a no-op."""
    pass
