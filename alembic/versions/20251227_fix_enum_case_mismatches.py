"""Fix enum case mismatches between Python code and database.

Revision ID: fix_enum_case_001
Revises:
Create Date: 2025-12-27

This migration adds missing enum values to match what the Python code expects.
The issue is that some enums have uppercase values in DB but Python sends lowercase.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'fix_enum_case_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add missing enum values to fix case mismatches."""

    # Fix paymentstatus enum - add lowercase versions if they don't exist
    # DB has: COMPLETED, FAILED, PENDING, REFUNDED, approved, posted
    # Need to add: completed, failed, pending, refunded (lowercase versions)
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'completed'")
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'failed'")
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'pending'")
    op.execute("ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'refunded'")

    # Fix attendancestatus enum - add lowercase versions
    # DB has: ABSENT, HALF_DAY, ON_LEAVE, PRESENT, WORK_FROM_HOME (uppercase)
    # Python expects: absent, half_day, on_leave, present, work_from_home (lowercase)
    op.execute("ALTER TYPE attendancestatus ADD VALUE IF NOT EXISTS 'present'")
    op.execute("ALTER TYPE attendancestatus ADD VALUE IF NOT EXISTS 'absent'")
    op.execute("ALTER TYPE attendancestatus ADD VALUE IF NOT EXISTS 'on_leave'")
    op.execute("ALTER TYPE attendancestatus ADD VALUE IF NOT EXISTS 'half_day'")
    op.execute("ALTER TYPE attendancestatus ADD VALUE IF NOT EXISTS 'work_from_home'")

    # Fix taskstatus enum - add lowercase versions
    # DB has: CANCELLED, COMPLETED, OPEN, OVERDUE, PENDING_REVIEW, TEMPLATE, WORKING
    # Python might expect lowercase versions
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'open'")
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'working'")
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'pending_review'")
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'completed'")
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'cancelled'")
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'overdue'")
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'template'")


def downgrade():
    """Cannot remove enum values in PostgreSQL, so this is a no-op."""
    pass
