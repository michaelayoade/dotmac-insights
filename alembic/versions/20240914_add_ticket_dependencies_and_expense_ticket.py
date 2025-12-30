"""Add HD Ticket dependencies table and ticket linkage to expenses.

Revision ID: 20240914_ticket_deps_expense
Revises: 20240912_hd_ticket_children, 20240913_expenses_audit_writeback
Create Date: 2025-12-12

Adds:
- hd_ticket_dependencies table for HD Ticket 'Depends On' child table
- ticket_id and erpnext_ticket columns to expenses table
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20240914_ticket_deps_expense"
down_revision: Union[str, Sequence[str], None] = (
    "20240912_hd_ticket_children",
    "20240913_expenses_audit_writeback",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create hd_ticket_dependencies table
    op.create_table(
        "hd_ticket_dependencies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("erpnext_name", sa.String(255), nullable=True),
        sa.Column("depends_on_ticket_id", sa.Integer(), nullable=True),
        sa.Column("depends_on_erpnext_id", sa.String(100), nullable=True),
        sa.Column("depends_on_subject", sa.String(500), nullable=True),
        sa.Column("depends_on_status", sa.String(50), nullable=True),
        sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_ticket_id"], ["tickets.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_hd_ticket_dependencies_id", "hd_ticket_dependencies", ["id"])
    op.create_index("ix_hd_ticket_dependencies_ticket_id", "hd_ticket_dependencies", ["ticket_id"])
    op.create_index("ix_hd_ticket_dependencies_erpnext_name", "hd_ticket_dependencies", ["erpnext_name"])
    op.create_index("ix_hd_ticket_dependencies_depends_on_ticket_id", "hd_ticket_dependencies", ["depends_on_ticket_id"])
    op.create_index("ix_hd_ticket_dependencies_depends_on_erpnext_id", "hd_ticket_dependencies", ["depends_on_erpnext_id"])

    # Add ticket linkage columns to expenses table
    op.add_column("expenses", sa.Column("ticket_id", sa.Integer(), nullable=True))
    op.add_column("expenses", sa.Column("erpnext_ticket", sa.String(255), nullable=True))
    op.create_index("ix_expenses_ticket_id", "expenses", ["ticket_id"])
    op.create_index("ix_expenses_erpnext_ticket", "expenses", ["erpnext_ticket"])
    op.create_foreign_key(
        "fk_expenses_ticket_id",
        "expenses",
        "tickets",
        ["ticket_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Remove ticket linkage from expenses
    op.drop_constraint("fk_expenses_ticket_id", "expenses", type_="foreignkey")
    op.drop_index("ix_expenses_erpnext_ticket", table_name="expenses")
    op.drop_index("ix_expenses_ticket_id", table_name="expenses")
    op.drop_column("expenses", "erpnext_ticket")
    op.drop_column("expenses", "ticket_id")

    # Drop hd_ticket_dependencies table
    op.drop_index("ix_hd_ticket_dependencies_depends_on_erpnext_id", table_name="hd_ticket_dependencies")
    op.drop_index("ix_hd_ticket_dependencies_depends_on_ticket_id", table_name="hd_ticket_dependencies")
    op.drop_index("ix_hd_ticket_dependencies_erpnext_name", table_name="hd_ticket_dependencies")
    op.drop_index("ix_hd_ticket_dependencies_ticket_id", table_name="hd_ticket_dependencies")
    op.drop_index("ix_hd_ticket_dependencies_id", table_name="hd_ticket_dependencies")
    op.drop_table("hd_ticket_dependencies")
