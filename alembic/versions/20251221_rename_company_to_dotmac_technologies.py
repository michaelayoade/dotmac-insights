"""Rename company values from DotMac Limited to Dotmac Technologies.

Revision ID: 20251221_rename_company_to_dotmac_technologies
Revises: fcaad815e605
Create Date: 2025-12-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20251221_rename_company_to_dotmac_technologies"
down_revision: Union[str, None] = "fcaad815e605"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_COMPANY = "DotMac Limited"
NEW_COMPANY = "Dotmac Technologies"


def upgrade() -> None:
    """Update existing company values."""
    bind = op.get_bind()
    inspector = inspect(bind)

    tables = [
        row[0]
        for row in bind.execute(
            sa.text(
                """
                SELECT table_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND column_name = 'company'
                ORDER BY table_name
                """
            )
        ).fetchall()
    ]

    for table in tables:
        if not inspector.has_table(table):
            continue
        bind.execute(
            sa.text(f"UPDATE {table} SET company = :new WHERE company = :old"),
            {"new": NEW_COMPANY, "old": OLD_COMPANY},
        )


def downgrade() -> None:
    """Revert company rename."""
    bind = op.get_bind()
    inspector = inspect(bind)

    tables = [
        row[0]
        for row in bind.execute(
            sa.text(
                """
                SELECT table_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND column_name = 'company'
                ORDER BY table_name
                """
            )
        ).fetchall()
    ]

    for table in tables:
        if not inspector.has_table(table):
            continue
        bind.execute(
            sa.text(f"UPDATE {table} SET company = :old WHERE company = :new"),
            {"new": NEW_COMPANY, "old": OLD_COMPANY},
        )
