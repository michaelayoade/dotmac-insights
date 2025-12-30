"""Add self-reference CHECK constraints for hierarchy tables

Revision ID: 20251218_hierarchy_checks
Revises: 20251218_add_cascade_policies
Create Date: 2025-12-18

Adds CHECK constraints to prevent direct self-reference in hierarchical tables:
- unified_contacts: parent_id != id
- tasks: parent_task_id != id
- tickets: parent_ticket_id != id
- employees: reports_to_id != id

Note: These constraints prevent direct self-reference only.
For deeper cycle detection (A->B->C->A), use the app-layer
validate_no_circular_reference() function before updates.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20251218_hierarchy_checks"
down_revision: Union[str, None] = "20251218_add_cascade_policies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CHECK constraints to prevent direct self-reference."""
    # unified_contacts: parent_id cannot equal own id
    op.execute("""
        ALTER TABLE unified_contacts
        ADD CONSTRAINT chk_unified_contacts_no_self_parent
        CHECK (parent_id IS NULL OR parent_id != id)
    """)

    # tasks: parent_task_id cannot equal own id
    op.execute("""
        ALTER TABLE tasks
        ADD CONSTRAINT chk_tasks_no_self_parent
        CHECK (parent_task_id IS NULL OR parent_task_id != id)
    """)

    # tickets: parent_ticket_id cannot equal own id
    op.execute("""
        ALTER TABLE tickets
        ADD CONSTRAINT chk_tickets_no_self_parent
        CHECK (parent_ticket_id IS NULL OR parent_ticket_id != id)
    """)

    # employees: reports_to_id cannot equal own id
    op.execute("""
        ALTER TABLE employees
        ADD CONSTRAINT chk_employees_no_self_manager
        CHECK (reports_to_id IS NULL OR reports_to_id != id)
    """)


def downgrade() -> None:
    """Remove self-reference CHECK constraints."""
    op.execute("ALTER TABLE employees DROP CONSTRAINT IF EXISTS chk_employees_no_self_manager")
    op.execute("ALTER TABLE tickets DROP CONSTRAINT IF EXISTS chk_tickets_no_self_parent")
    op.execute("ALTER TABLE tasks DROP CONSTRAINT IF EXISTS chk_tasks_no_self_parent")
    op.execute("ALTER TABLE unified_contacts DROP CONSTRAINT IF EXISTS chk_unified_contacts_no_self_parent")
