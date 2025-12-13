"""add_reports_permission

Revision ID: c2d3e4f5g6h7
Revises: g2h3i4j5k6l7
Create Date: 2025-12-12 17:00:00.000000

Seeds the reports:read permission for the consolidated reports API.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5g6h7'
down_revision: Union[str, None] = 'g2h3i4j5k6l7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add reports:read permission and assign to admin, operator, analyst roles."""
    connection = op.get_bind()
    now = datetime.utcnow()

    # Check if permission already exists
    existing = connection.execute(
        sa.text("SELECT id FROM permissions WHERE scope = 'reports:read'")
    ).fetchone()

    if not existing:
        # Insert the reports:read permission
        connection.execute(
            sa.text("""
                INSERT INTO permissions (scope, description, category, created_at)
                VALUES (:scope, :description, :category, :created_at)
            """),
            {
                "scope": "reports:read",
                "description": "View consolidated financial reports (revenue, expenses, profitability, cash position)",
                "category": "reports",
                "created_at": now,
            }
        )

        # Get the permission ID
        perm_result = connection.execute(
            sa.text("SELECT id FROM permissions WHERE scope = 'reports:read'")
        ).fetchone()

        if perm_result:
            perm_id = perm_result[0]

            # Assign to admin, operator, and analyst roles
            roles_to_assign = ['admin', 'operator', 'analyst']
            for role_name in roles_to_assign:
                role_result = connection.execute(
                    sa.text("SELECT id FROM roles WHERE name = :name"),
                    {"name": role_name}
                ).fetchone()

                if role_result:
                    role_id = role_result[0]
                    # Check if mapping already exists
                    existing_mapping = connection.execute(
                        sa.text("""
                            SELECT id FROM role_permissions
                            WHERE role_id = :role_id AND permission_id = :perm_id
                        """),
                        {"role_id": role_id, "perm_id": perm_id}
                    ).fetchone()

                    if not existing_mapping:
                        connection.execute(
                            sa.text("""
                                INSERT INTO role_permissions (role_id, permission_id, created_at)
                                VALUES (:role_id, :perm_id, :created_at)
                            """),
                            {"role_id": role_id, "perm_id": perm_id, "created_at": now}
                        )


def downgrade() -> None:
    """Remove reports:read permission and its role mappings."""
    connection = op.get_bind()

    # Get the permission ID
    perm_result = connection.execute(
        sa.text("SELECT id FROM permissions WHERE scope = 'reports:read'")
    ).fetchone()

    if perm_result:
        perm_id = perm_result[0]

        # Remove role-permission mappings
        connection.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :perm_id"),
            {"perm_id": perm_id}
        )

        # Remove the permission
        connection.execute(
            sa.text("DELETE FROM permissions WHERE id = :perm_id"),
            {"perm_id": perm_id}
        )
