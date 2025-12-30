"""Merge uc003_enforce_not_null and perf001_performance_module

This migration resolves the diverging heads created when both:
- uc003_enforce_not_null (unified contact NOT NULL enforcement)
- perf001_performance_module (performance management tables)

were created with the same down_revision (uc002_migrate_contacts).

Revision ID: merge_uc003_perf001
Revises: uc003_enforce_not_null, perf001_performance_module
Create Date: 2025-12-17
"""
from alembic import op
import sqlalchemy as sa

revision = 'merge_uc003_perf001'
down_revision = ('uc003_enforce_not_null', 'perf001_performance_module')
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge point - no schema changes needed."""
    pass


def downgrade() -> None:
    """Merge point - no schema changes needed."""
    pass
