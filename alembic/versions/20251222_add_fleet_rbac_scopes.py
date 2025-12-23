"""Add fleet RBAC scopes

Revision ID: 20251222_add_fleet_rbac_scopes
Revises: 20251222_enforce_supplier_group_not_null
Create Date: 2025-12-22

Adds dedicated RBAC scopes for Fleet module:
- fleet:read - View vehicles, drivers, insurance
- fleet:write - Manage vehicles and assignments
"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa
from datetime import datetime


revision: str = "20251222_add_fleet_rbac_scopes"
down_revision: Union[str, None] = "20251222_enforce_supplier_group_not_null"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Fleet permissions to add
NEW_PERMISSIONS = [
    ("fleet:read", "View vehicles, drivers, and insurance", "fleet"),
    ("fleet:write", "Manage vehicles and driver assignments", "fleet"),
]


# Role assignments for new permissions
ROLE_PERMISSIONS = {
    "admin": ["fleet:read", "fleet:write"],
    "operator": ["fleet:read", "fleet:write"],
    "analyst": ["fleet:read"],
    "viewer": ["fleet:read"],
}


def upgrade() -> None:
    """Add fleet RBAC permissions and assign to roles."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return
    now = datetime.utcnow()

    def fetchall_safe(statement: str, params: dict | None = None):
        """Run a query defensively; return [] if the connection is a mock/offline handle."""
        try:
            result = connection.execute(sa.text(statement), params or {})
            return result.fetchall() if result is not None else []
        except AttributeError:
            return []

    # Insert new permissions (idempotent via ON CONFLICT)
    for scope, description, category in NEW_PERMISSIONS:
        connection.execute(
            sa.text("""
                INSERT INTO permissions (scope, description, category, created_at)
                VALUES (:scope, :description, :category, :created_at)
                ON CONFLICT (scope) DO NOTHING
            """),
            {"scope": scope, "description": description, "category": category, "created_at": now}
        )

    # Get permission IDs for newly added scopes
    scopes_list = [p[0] for p in NEW_PERMISSIONS]
    placeholders = ",".join([f"'{s}'" for s in scopes_list])
    perms_result = fetchall_safe(f"SELECT id, scope FROM permissions WHERE scope IN ({placeholders})")
    perm_id_map = {row[1]: row[0] for row in perms_result}

    # Get role IDs
    roles_result = fetchall_safe(
        "SELECT id, name FROM roles WHERE name IN ('admin', 'operator', 'analyst', 'viewer')"
    )
    role_id_map = {row[1]: row[0] for row in roles_result}

    # Assign permissions to roles (idempotent)
    for role_name, scopes in ROLE_PERMISSIONS.items():
        role_id = role_id_map.get(role_name)
        if role_id:
            for scope in scopes:
                perm_id = perm_id_map.get(scope)
                if perm_id:
                    # Check if mapping already exists
                    exists = connection.execute(
                        sa.text("""
                            SELECT 1 FROM role_permissions
                            WHERE role_id = :role_id AND permission_id = :perm_id
                        """),
                        {"role_id": role_id, "perm_id": perm_id}
                    ).fetchone()

                    if not exists:
                        connection.execute(
                            sa.text("""
                                INSERT INTO role_permissions (role_id, permission_id, created_at)
                                VALUES (:role_id, :perm_id, :created_at)
                            """),
                            {"role_id": role_id, "perm_id": perm_id, "created_at": now}
                        )


def downgrade() -> None:
    """Remove fleet RBAC permissions."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    scopes_to_remove = [p[0] for p in NEW_PERMISSIONS]

    # Get permission IDs
    placeholders = ",".join([f"'{s}'" for s in scopes_to_remove])
    perms_result = connection.execute(
        sa.text(f"SELECT id FROM permissions WHERE scope IN ({placeholders})")
    ).fetchall()
    perm_ids = [row[0] for row in perms_result]

    if perm_ids:
        perm_ids_str = ",".join([str(p) for p in perm_ids])

        # Delete role-permission mappings
        connection.execute(
            sa.text(f"DELETE FROM role_permissions WHERE permission_id IN ({perm_ids_str})")
        )

        # Delete permissions
        connection.execute(
            sa.text(f"DELETE FROM permissions WHERE id IN ({perm_ids_str})")
        )
