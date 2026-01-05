"""Add company field to employees table.

Revision ID: add_employee_company
Revises:
Create Date: 2026-01-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_employee_company"
down_revision = "92f0d830518f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add company column to employees table
    op.add_column(
        "employees",
        sa.Column("company", sa.String(255), nullable=True)
    )

    # Create index for company
    op.create_index(
        "ix_employees_company",
        "employees",
        ["company"]
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_employees_company", table_name="employees")

    # Drop column
    op.drop_column("employees", "company")
