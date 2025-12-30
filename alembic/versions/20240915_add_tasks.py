"""Add tasks and task_dependencies tables, and expense task/ticket links

Revision ID: 20240915_add_tasks
Revises: 20240914_ticket_deps_expense
Create Date: 2024-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20240915_add_tasks"
down_revision: Union[str, None] = "20240914_ticket_deps_expense"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tasks table
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("erpnext_id", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("erpnext_project", sa.String(255), nullable=True),
        sa.Column("issue", sa.String(255), nullable=True),
        sa.Column("task_type", sa.String(255), nullable=True),
        sa.Column("color", sa.String(50), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN", "WORKING", "PENDING_REVIEW", "OVERDUE", "TEMPLATE", "COMPLETED", "CANCELLED",
                name="taskstatus"
            ),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column(
            "priority",
            sa.Enum("LOW", "MEDIUM", "HIGH", "URGENT", name="taskpriority"),
            nullable=False,
            server_default="MEDIUM",
        ),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("completed_by", sa.String(255), nullable=True),
        sa.Column("progress", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("expected_time", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("actual_time", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("exp_start_date", sa.Date(), nullable=True),
        sa.Column("exp_end_date", sa.Date(), nullable=True),
        sa.Column("act_start_date", sa.Date(), nullable=True),
        sa.Column("act_end_date", sa.Date(), nullable=True),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("closing_date", sa.Date(), nullable=True),
        sa.Column("parent_task", sa.String(255), nullable=True),
        sa.Column("parent_task_id", sa.Integer(), nullable=True),
        sa.Column("is_group", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("total_costing_amount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total_billing_amount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total_expense_claim", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("template_task", sa.String(255), nullable=True),
        sa.Column("docstatus", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lft", sa.Integer(), nullable=True),
        sa.Column("rgt", sa.Integer(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["parent_task_id"], ["tasks.id"]),
    )
    op.create_index("ix_tasks_id", "tasks", ["id"])
    op.create_index("ix_tasks_erpnext_id", "tasks", ["erpnext_id"], unique=True)
    op.create_index("ix_tasks_subject", "tasks", ["subject"])
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_erpnext_project", "tasks", ["erpnext_project"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_priority", "tasks", ["priority"])
    op.create_index("ix_tasks_assigned_to", "tasks", ["assigned_to"])
    op.create_index("ix_tasks_exp_start_date", "tasks", ["exp_start_date"])
    op.create_index("ix_tasks_exp_end_date", "tasks", ["exp_end_date"])
    op.create_index("ix_tasks_parent_task", "tasks", ["parent_task"])
    op.create_index("ix_tasks_parent_task_id", "tasks", ["parent_task_id"])

    # Create task_dependencies table
    op.create_table(
        "task_dependencies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("dependent_task_id", sa.Integer(), nullable=True),
        sa.Column("dependent_task_erpnext", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("project", sa.String(255), nullable=True),
        sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("erpnext_name", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dependent_task_id"], ["tasks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_task_dependencies_id", "task_dependencies", ["id"])
    op.create_index("ix_task_dependencies_task_id", "task_dependencies", ["task_id"])
    op.create_index("ix_task_dependencies_dependent_task_id", "task_dependencies", ["dependent_task_id"])

    # Add task_id column to expenses table
    # Rename existing 'task' column to 'erpnext_task' (model expects erpnext_task not task)
    op.alter_column("expenses", "task", new_column_name="erpnext_task")
    op.add_column("expenses", sa.Column("task_id", sa.Integer(), nullable=True))

    op.create_foreign_key(
        "fk_expenses_task_id", "expenses", "tasks", ["task_id"], ["id"]
    )
    op.create_index("ix_expenses_task_id", "expenses", ["task_id"])
    op.create_index("ix_expenses_erpnext_task", "expenses", ["erpnext_task"])


def downgrade() -> None:
    # Drop expense columns and FKs
    op.drop_index("ix_expenses_erpnext_task", table_name="expenses")
    op.drop_index("ix_expenses_task_id", table_name="expenses")
    op.drop_constraint("fk_expenses_task_id", "expenses", type_="foreignkey")
    op.drop_column("expenses", "task_id")
    # Rename erpnext_task back to task
    op.alter_column("expenses", "erpnext_task", new_column_name="task")

    # Drop task_dependencies table
    op.drop_index("ix_task_dependencies_dependent_task_id", table_name="task_dependencies")
    op.drop_index("ix_task_dependencies_task_id", table_name="task_dependencies")
    op.drop_index("ix_task_dependencies_id", table_name="task_dependencies")
    op.drop_table("task_dependencies")

    # Drop tasks table
    op.drop_index("ix_tasks_parent_task_id", table_name="tasks")
    op.drop_index("ix_tasks_parent_task", table_name="tasks")
    op.drop_index("ix_tasks_exp_end_date", table_name="tasks")
    op.drop_index("ix_tasks_exp_start_date", table_name="tasks")
    op.drop_index("ix_tasks_assigned_to", table_name="tasks")
    op.drop_index("ix_tasks_priority", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_erpnext_project", table_name="tasks")
    op.drop_index("ix_tasks_project_id", table_name="tasks")
    op.drop_index("ix_tasks_subject", table_name="tasks")
    op.drop_index("ix_tasks_erpnext_id", table_name="tasks")
    op.drop_index("ix_tasks_id", table_name="tasks")
    op.drop_table("tasks")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS taskpriority")
    op.execute("DROP TYPE IF EXISTS taskstatus")
