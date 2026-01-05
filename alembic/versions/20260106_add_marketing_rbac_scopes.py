"""Add marketing module RBAC scopes

Adds the marketing:read permission required to access the Marketing module UI
and API endpoints.

Revision ID: 20260106_add_marketing_rbac
Revises: 20260105_merge_all_heads_v2
Create Date: 2026-01-06
"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa
from datetime import datetime


revision: str = "20260106_add_marketing_rbac"
down_revision: Union[str, None] = "20260105_merge_all_heads_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MARKETING_PERMISSIONS = [
    ("marketing:read", "View marketing dashboards, journeys, campaigns, and channels", "marketing"),
    ("marketing:write", "Create and manage marketing journeys, campaigns, and channels", "marketing"),
]

ROLE_MARKETING_PERMISSIONS = {
    "admin": ["marketing:read", "marketing:write"],
    "operator": ["marketing:read", "marketing:write"],
    "analyst": ["marketing:read"],
    "viewer": ["marketing:read"],
}


def upgrade() -> None:
    """Add marketing permissions and role mappings."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    now = datetime.utcnow()

    for scope, description, category in MARKETING_PERMISSIONS:
        connection.execute(
            sa.text("""
                INSERT INTO permissions (scope, description, category, created_at)
                VALUES (:scope, :description, :category, :created_at)
                ON CONFLICT (scope) DO UPDATE SET
                    description = EXCLUDED.description,
                    category = EXCLUDED.category
            """),
            {"scope": scope, "description": description, "category": category, "created_at": now},
        )

    roles_result = connection.execute(
        sa.text("SELECT id, name FROM roles WHERE name IN ('admin', 'operator', 'analyst', 'viewer')")
    ).fetchall()
    role_id_map = {row[1]: row[0] for row in roles_result}

    perms_result = connection.execute(
        sa.text("SELECT id, scope FROM permissions WHERE scope LIKE 'marketing:%'")
    ).fetchall()
    perm_id_map = {row[1]: row[0] for row in perms_result}

    for role_name, scopes in ROLE_MARKETING_PERMISSIONS.items():
        role_id = role_id_map.get(role_name)
        if not role_id:
            continue

        for scope in scopes:
            perm_id = perm_id_map.get(scope)
            if not perm_id:
                continue

            connection.execute(
                sa.text("""
                    INSERT INTO role_permissions (role_id, permission_id, created_at)
                    VALUES (:role_id, :perm_id, :created_at)
                    ON CONFLICT DO NOTHING
                """),
                {"role_id": role_id, "perm_id": perm_id, "created_at": now},
            )



def downgrade() -> None:
    """Remove marketing permissions and role mappings."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    perms_result = connection.execute(
        sa.text("SELECT id FROM permissions WHERE scope LIKE 'marketing:%'")
    ).fetchall()
    perm_ids = [row[0] for row in perms_result]

    if perm_ids:
        for perm_id in perm_ids:
            connection.execute(
                sa.text("DELETE FROM role_permissions WHERE permission_id = :perm_id"),
                {"perm_id": perm_id},
            )

        for perm_id in perm_ids:
            connection.execute(
                sa.text("DELETE FROM permissions WHERE id = :perm_id"),
                {"perm_id": perm_id},
            )
