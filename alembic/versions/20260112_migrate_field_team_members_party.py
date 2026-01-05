"""Migrate field team members to party IDs.

Revision ID: 20260112_migrate_field_team_members_party
Revises: 20260111_add_activity_log
Create Date: 2026-01-12
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260112_migrate_field_team_members_party"
down_revision = "20260111_add_activity_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("field_team_members", sa.Column("party_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_field_team_members_party_id", "field_team_members", ["party_id"])
    op.create_foreign_key(
        "fk_field_team_members_party_id",
        "field_team_members",
        "parties",
        ["party_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute(
        """
        UPDATE field_team_members ftm
        SET party_id = e.party_id
        FROM employees e
        WHERE ftm.employee_id = e.id
        """
    )

    op.drop_index("ix_field_team_members_team_employee", table_name="field_team_members")
    op.create_index(
        "ix_field_team_members_team_party",
        "field_team_members",
        ["team_id", "party_id"],
        unique=True,
    )

    op.drop_constraint("field_team_members_employee_id_fkey", "field_team_members", type_="foreignkey")
    op.drop_index("ix_field_team_members_employee_id", table_name="field_team_members")
    op.drop_column("field_team_members", "employee_id")


def downgrade() -> None:
    op.add_column("field_team_members", sa.Column("employee_id", sa.Integer(), nullable=True))
    op.create_index("ix_field_team_members_employee_id", "field_team_members", ["employee_id"])
    op.create_foreign_key(
        "field_team_members_employee_id_fkey",
        "field_team_members",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute(
        """
        UPDATE field_team_members ftm
        SET employee_id = e.id
        FROM employees e
        WHERE ftm.party_id = e.party_id
        """
    )

    op.drop_index("ix_field_team_members_team_party", table_name="field_team_members")
    op.create_index(
        "ix_field_team_members_team_employee",
        "field_team_members",
        ["team_id", "employee_id"],
        unique=True,
    )

    op.drop_constraint("fk_field_team_members_party_id", "field_team_members", type_="foreignkey")
    op.drop_index("ix_field_team_members_party_id", table_name="field_team_members")
    op.drop_column("field_team_members", "party_id")
