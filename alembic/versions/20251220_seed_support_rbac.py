"""Seed support module RBAC scopes and role mappings.

Revision ID: 20251220_seed_support_rbac
Revises: 20251220_merge_support_heads
Create Date: 2025-12-20
"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa
from datetime import datetime


revision: str = "20251220_seed_support_rbac"
down_revision: Union[str, None] = "20251220_merge_support_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SUPPORT_PERMISSIONS = [
    ("support:read", "View inbox conversations, contacts, routing rules, and analytics", "support"),
    ("support:write", "Create and update inbox conversations, contacts, and routing rules", "support"),
]

ROLE_SUPPORT_PERMISSIONS = {
    "admin": ["support:read", "support:write"],
    "operator": ["support:read", "support:write"],
    "analyst": ["support:read"],
    "viewer": ["support:read"],
}


def upgrade() -> None:
    """Seed support permissions and role mappings."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    now = datetime.utcnow()

    for scope, description, category in SUPPORT_PERMISSIONS:
        connection.execute(
            sa.text("""
                INSERT INTO permissions (scope, description, category, created_at)
                VALUES (:scope, :description, :category, :created_at)
                ON CONFLICT (scope) DO UPDATE SET
                    description = EXCLUDED.description,
                    category = EXCLUDED.category
            """),
            {"scope": scope, "description": description, "category": category, "created_at": now}
        )

    roles_result = connection.execute(
        sa.text("SELECT id, name FROM roles WHERE name IN ('admin', 'operator', 'analyst', 'viewer')")
    ).fetchall()
    role_id_map = {row[1]: row[0] for row in roles_result}

    perms_result = connection.execute(
        sa.text("SELECT id, scope FROM permissions WHERE scope IN ('support:read', 'support:write')")
    ).fetchall()
    perm_id_map = {row[1]: row[0] for row in perms_result}

    for role_name, scopes in ROLE_SUPPORT_PERMISSIONS.items():
        role_id = role_id_map.get(role_name)
        if not role_id:
            continue
        for scope in scopes:
            perm_id = perm_id_map.get(scope)
            if not perm_id:
                continue
            connection.execute(
                sa.text("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES (:role_id, :permission_id)
                    ON CONFLICT DO NOTHING
                """),
                {"role_id": role_id, "permission_id": perm_id}
            )


def downgrade() -> None:
    """Remove support permissions and role mappings."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    perms_result = connection.execute(
        sa.text("SELECT id FROM permissions WHERE scope IN ('support:read', 'support:write')")
    ).fetchall()
    perm_ids = [row[0] for row in perms_result]

    if perm_ids:
        connection.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = ANY(:perm_ids)"),
            {"perm_ids": perm_ids}
        )
        connection.execute(
            sa.text("DELETE FROM permissions WHERE scope IN ('support:read', 'support:write')")
        )
