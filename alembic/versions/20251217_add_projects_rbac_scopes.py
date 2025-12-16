"""add_projects_rbac_scopes

Revision ID: 20251217_add_projects_rbac_scopes
Revises: 20251217_add_crm_rbac_scopes
Create Date: 2024-12-17

Adds RBAC scopes for Projects module:
- projects:read - View projects and tasks
- projects:write - Create/update/delete projects and tasks
- projects:admin - Project administration
"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = "20251217_add_projects_rbac_scopes"
down_revision: Union[str, None] = "20251217_add_crm_rbac_scopes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Projects permissions to add
PROJECTS_PERMISSIONS = [
    ("projects:read", "View projects, tasks, and project analytics", "projects"),
    ("projects:write", "Create, update, and delete projects and tasks", "projects"),
    ("projects:admin", "Full project administration", "projects"),
]

# Role assignments for projects permissions
ROLE_PROJECTS_PERMISSIONS = {
    "admin": ["projects:read", "projects:write", "projects:admin"],
    "operator": ["projects:read", "projects:write"],
    "analyst": ["projects:read"],
    "viewer": ["projects:read"],
}


def upgrade() -> None:
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

    # Insert new permissions
    for scope, description, category in PROJECTS_PERMISSIONS:
        connection.execute(
            sa.text("""
                INSERT INTO permissions (scope, description, category, created_at)
                VALUES (:scope, :description, :category, :created_at)
                ON CONFLICT (scope) DO NOTHING
            """),
            {"scope": scope, "description": description, "category": category, "created_at": now}
        )

    # Get permission IDs
    perms_result = fetchall_safe("SELECT id, scope FROM permissions WHERE scope LIKE 'projects:%'")
    perm_id_map = {row[1]: row[0] for row in perms_result}

    # Get role IDs
    roles_result = fetchall_safe(
        "SELECT id, name FROM roles WHERE name IN ('admin', 'operator', 'analyst', 'viewer')"
    )
    role_id_map = {row[1]: row[0] for row in roles_result}

    # Assign permissions to roles
    for role_name, scopes in ROLE_PROJECTS_PERMISSIONS.items():
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
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    # Get permission IDs for projects scopes
    perms_result = connection.execute(
        sa.text("SELECT id FROM permissions WHERE scope LIKE 'projects:%'")
    ).fetchall()
    perm_ids = [row[0] for row in perms_result]

    if perm_ids:
        # Delete role-permission mappings
        connection.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = ANY(:perm_ids)"),
            {"perm_ids": perm_ids}
        )

        # Delete permissions
        connection.execute(
            sa.text("DELETE FROM permissions WHERE id = ANY(:perm_ids)"),
            {"perm_ids": perm_ids}
        )
