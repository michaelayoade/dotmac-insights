"""Align enum values across known types by adding missing case variants.

Revision ID: 20260308_align_enum_cases
Revises: 20260308_add_milestone_enum_case
Create Date: 2026-03-08

This migration inspects known enum types and adds missing values so
Python models and database enums stay compatible regardless of case.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260308_align_enum_cases"
down_revision = "20260308_add_milestone_enum_case"
branch_labels = None
depends_on = None


def _enum_exists(conn, enum_name: str) -> bool:
    return conn.execute(
        sa.text("SELECT to_regtype(:name) IS NOT NULL"),
        {"name": enum_name},
    ).scalar() is True


def _get_enum_labels(conn, enum_name: str) -> set[str]:
    rows = conn.execute(
        sa.text(
            "SELECT enumlabel FROM pg_enum "
            "WHERE enumtypid = to_regtype(:name)"
        ),
        {"name": enum_name},
    ).fetchall()
    return {row[0] for row in rows}


def _ensure_enum_values(conn, enum_name: str, values: list[str]) -> None:
    if not _enum_exists(conn, enum_name):
        return

    existing = _get_enum_labels(conn, enum_name)
    for value in values:
        if value in existing:
            continue
        conn.execute(
            sa.text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")
        )


def upgrade() -> None:
    conn = op.get_bind()

    enum_values = {
        "projectstatus": [
            "OPEN", "COMPLETED", "CANCELLED", "ON_HOLD",
            "open", "completed", "cancelled", "on_hold",
        ],
        "projectpriority": [
            "LOW", "MEDIUM", "HIGH",
            "low", "medium", "high",
        ],
        "milestonestatus": [
            "planned", "in_progress", "completed", "on_hold",
            "PLANNED", "IN_PROGRESS", "COMPLETED", "ON_HOLD",
        ],
        "taskstatus": [
            "OPEN", "WORKING", "PENDING_REVIEW", "COMPLETED", "CANCELLED", "OVERDUE", "TEMPLATE",
            "open", "working", "pending_review", "completed", "cancelled", "overdue", "template",
        ],
        "paymentstatus": [
            "PENDING", "APPROVED", "POSTED", "COMPLETED", "FAILED", "REFUNDED",
            "pending", "approved", "posted", "completed", "failed", "refunded",
        ],
        "attendancestatus": [
            "PRESENT", "ABSENT", "ON_LEAVE", "HALF_DAY", "WORK_FROM_HOME",
            "present", "absent", "on_leave", "half_day", "work_from_home",
        ],
    }

    for enum_name, values in enum_values.items():
        _ensure_enum_values(conn, enum_name, values)


def downgrade() -> None:
    """Cannot remove enum values in PostgreSQL, so this is a no-op."""
    pass
