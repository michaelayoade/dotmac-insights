"""Add party_id to employees table.

Revision ID: add_employee_party_id
Revises:
Create Date: 2026-01-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_employee_party_id"
down_revision = "add_employee_company"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add party_id column to employees table
    op.add_column(
        "employees",
        sa.Column("party_id", sa.BigInteger(), nullable=True)
    )

    # Create index for party_id
    op.create_index(
        "ix_employees_party_id",
        "employees",
        ["party_id"]
    )

    # Create foreign key constraint
    op.create_foreign_key(
        "fk_employees_party_id",
        "employees",
        "parties",
        ["party_id"],
        ["id"],
        ondelete="SET NULL"
    )


def downgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint("fk_employees_party_id", "employees", type_="foreignkey")

    # Drop index
    op.drop_index("ix_employees_party_id", table_name="employees")

    # Drop column
    op.drop_column("employees", "party_id")
