"""Add support module RBAC scopes

Adds the missing support:read and support:write permissions
that are required by the inbox API routes but were not seeded.

The inbox API uses support:* permissions for:
- conversations (list, create, update)
- analytics (summary, volume, agents, channels)
- contacts (list, create, update)
- routing rules (list, create, update)

Revision ID: 20251220_add_support_rbac
Revises: m8n9o0p1q2r3
Create Date: 2025-12-20
"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa
from datetime import datetime


revision: str = "20251220_add_support_rbac"
down_revision: Union[str, None] = "m8n9o0p1q2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Support permissions required by inbox API routes
SUPPORT_PERMISSIONS = [
    ("support:read", "View inbox conversations, contacts, routing rules, and analytics", "support"),
    ("support:write", "Create and update inbox conversations, contacts, and routing rules", "support"),
]

# Role permission assignments - matching the pattern from tickets permissions
ROLE_SUPPORT_PERMISSIONS = {
    "admin": ["support:read", "support:write"],
    "operator": ["support:read", "support:write"],
    "analyst": ["support:read"],
    "viewer": ["support:read"],
}


def upgrade() -> None:
    """Add support permissions and role mappings."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    now = datetime.utcnow()

    # Insert support permissions
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

    # Get all role IDs
    roles_result = connection.execute(
        sa.text("SELECT id, name FROM roles WHERE name IN ('admin', 'operator', 'analyst', 'viewer')")
    ).fetchall()
    role_id_map = {row[1]: row[0] for row in roles_result}

    # Get support permission IDs
    perms_result = connection.execute(
        sa.text("SELECT id, scope FROM permissions WHERE scope LIKE 'support:%'")
    ).fetchall()
    perm_id_map = {row[1]: row[0] for row in perms_result}

    # Assign permissions to roles
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
                    INSERT INTO role_permissions (role_id, permission_id, created_at)
                    VALUES (:role_id, :perm_id, :created_at)
                    ON CONFLICT DO NOTHING
                """),
                {"role_id": role_id, "perm_id": perm_id, "created_at": now}
            )


def downgrade() -> None:
    """Remove support permissions and role mappings."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    # Get permission IDs for support scopes
    perms_result = connection.execute(
        sa.text("SELECT id FROM permissions WHERE scope LIKE 'support:%'")
    ).fetchall()
    perm_ids = [row[0] for row in perms_result]

    if perm_ids:
        # Delete role-permission mappings
        for perm_id in perm_ids:
            connection.execute(
                sa.text("DELETE FROM role_permissions WHERE permission_id = :perm_id"),
                {"perm_id": perm_id}
            )

        # Delete permissions
        for perm_id in perm_ids:
            connection.execute(
                sa.text("DELETE FROM permissions WHERE id = :perm_id"),
                {"perm_id": perm_id}
            )
