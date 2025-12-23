"""Seed supplier_groups and backfill supplier_group_id

Revision ID: cc3a9f8e3ad6
Revises: 20251222_add_missing_cross_module_fk_columns
Create Date: 2025-12-21 18:42:44.832627

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc3a9f8e3ad6'
down_revision: Union[str, None] = '20251222_add_missing_cross_module_fk_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: Get distinct supplier_group values that don't have a matching supplier_groups record
    result = conn.execute(
        sa.text("""
            SELECT DISTINCT s.supplier_group
            FROM suppliers s
            LEFT JOIN supplier_groups sg ON sg.name = s.supplier_group
            WHERE s.supplier_group IS NOT NULL
              AND s.supplier_group_id IS NULL
              AND sg.id IS NULL
        """)
    )
    missing_groups = [row[0] for row in result.fetchall()]

    # Step 2: Insert missing supplier_groups
    for group_name in missing_groups:
        conn.execute(
            sa.text("""
                INSERT INTO supplier_groups (name, is_group, created_at, updated_at)
                VALUES (:name, false, NOW(), NOW())
            """),
            {"name": group_name}
        )

    if missing_groups:
        print(f"  Inserted {len(missing_groups)} supplier_groups: {missing_groups}")

    # Step 3: Backfill supplier_group_id for all suppliers with matching supplier_group
    result = conn.execute(
        sa.text("""
            UPDATE suppliers s
            SET supplier_group_id = sg.id
            FROM supplier_groups sg
            WHERE s.supplier_group = sg.name
              AND s.supplier_group_id IS NULL
        """)
    )
    print(f"  Updated {result.rowcount} suppliers with supplier_group_id")


def downgrade() -> None:
    conn = op.get_bind()

    # Clear supplier_group_id values that were backfilled
    conn.execute(
        sa.text("""
            UPDATE suppliers
            SET supplier_group_id = NULL
            WHERE supplier_group_id IS NOT NULL
        """)
    )

    # Remove the seeded supplier_groups (only those with no erpnext_id)
    conn.execute(
        sa.text("""
            DELETE FROM supplier_groups
            WHERE erpnext_id IS NULL
              AND name IN ('All Supplier Groups', 'Services')
        """)
    )
