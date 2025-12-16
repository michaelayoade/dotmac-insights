"""seed_auth_rbac_defaults

Revision ID: f5545281ad87
Revises: d0b112dba8ae
Create Date: 2025-12-09 11:05:24.121523

Seeds default roles, permissions, and role-permission mappings for RBAC.
"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = 'f5545281ad87'
down_revision: Union[str, None] = 'd0b112dba8ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define default permissions with categories
DEFAULT_PERMISSIONS = [
    # Sync permissions
    ("sync:splynx:read", "View Splynx sync status", "sync"),
    ("sync:splynx:write", "Trigger Splynx syncs", "sync"),
    ("sync:erpnext:read", "View ERPNext sync status", "sync"),
    ("sync:erpnext:write", "Trigger ERPNext syncs", "sync"),
    ("sync:chatwoot:read", "View Chatwoot sync status", "sync"),
    ("sync:chatwoot:write", "Trigger Chatwoot syncs", "sync"),

    # Explorer permissions
    ("explorer:read", "View data in Data Explorer", "explorer"),
    ("explorer:export", "Export data from Explorer", "explorer"),

    # Analytics permissions
    ("analytics:read", "View analytics dashboards", "analytics"),
    ("analytics:export", "Export analytics data", "analytics"),

    # Admin permissions
    ("admin:users:read", "View user list", "admin"),
    ("admin:users:write", "Manage users (create, update, deactivate)", "admin"),
    ("admin:roles:read", "View roles and permissions", "admin"),
    ("admin:roles:write", "Manage roles and permissions", "admin"),
    ("admin:tokens:read", "View service tokens", "admin"),
    ("admin:tokens:write", "Manage service tokens", "admin"),
    ("admin:audit:read", "View audit logs", "admin"),
]


# Define default roles with descriptions
DEFAULT_ROLES = [
    ("admin", "Full system access - can manage users, roles, and all features", True),
    ("operator", "Can trigger syncs and view all data", True),
    ("analyst", "Read-only access to analytics and data explorer", True),
    ("viewer", "Read-only access to data explorer", True),
]


# Map roles to their permissions
ROLE_PERMISSIONS = {
    "admin": [
        "sync:splynx:read", "sync:splynx:write",
        "sync:erpnext:read", "sync:erpnext:write",
        "sync:chatwoot:read", "sync:chatwoot:write",
        "explorer:read", "explorer:export",
        "analytics:read", "analytics:export",
        "admin:users:read", "admin:users:write",
        "admin:roles:read", "admin:roles:write",
        "admin:tokens:read", "admin:tokens:write",
        "admin:audit:read",
    ],
    "operator": [
        "sync:splynx:read", "sync:splynx:write",
        "sync:erpnext:read", "sync:erpnext:write",
        "sync:chatwoot:read", "sync:chatwoot:write",
        "explorer:read", "explorer:export",
        "analytics:read",
    ],
    "analyst": [
        "explorer:read", "explorer:export",
        "analytics:read", "analytics:export",
    ],
    "viewer": [
        "explorer:read",
    ],
}


def upgrade() -> None:
    """Seed default permissions, roles, and role-permission mappings."""
    if context.is_offline_mode():
        # Skip data inserts in offline/--sql mode
        return

    connection = op.get_bind()
    now = datetime.utcnow()

    # Insert permissions
    permissions_table = sa.table(
        'permissions',
        sa.column('id', sa.Integer),
        sa.column('scope', sa.String),
        sa.column('description', sa.Text),
        sa.column('category', sa.String),
        sa.column('created_at', sa.DateTime),
    )

    # Check if permissions already exist
    existing = connection.execute(
        sa.text("SELECT scope FROM permissions WHERE scope = 'sync:splynx:read'")
    ).fetchone()

    if not existing:
        for scope, description, category in DEFAULT_PERMISSIONS:
            connection.execute(
                permissions_table.insert().values(
                    scope=scope,
                    description=description,
                    category=category,
                    created_at=now,
                )
            )

    # Insert roles
    roles_table = sa.table(
        'roles',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('description', sa.Text),
        sa.column('is_system', sa.Boolean),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime),
    )

    # Check if roles already exist
    existing_role = connection.execute(
        sa.text("SELECT name FROM roles WHERE name = 'admin'")
    ).fetchone()

    if not existing_role:
        for name, description, is_system in DEFAULT_ROLES:
            connection.execute(
                roles_table.insert().values(
                    name=name,
                    description=description,
                    is_system=is_system,
                    created_at=now,
                    updated_at=now,
                )
            )

    # Create role-permission mappings
    role_permissions_table = sa.table(
        'role_permissions',
        sa.column('id', sa.Integer),
        sa.column('role_id', sa.Integer),
        sa.column('permission_id', sa.Integer),
        sa.column('created_at', sa.DateTime),
    )

    # Check if mappings already exist
    existing_mapping = connection.execute(
        sa.text("SELECT COUNT(*) FROM role_permissions")
    ).scalar()

    if existing_mapping == 0:
        # Get role IDs
        roles_result = connection.execute(
            sa.text("SELECT id, name FROM roles")
        ).fetchall()
        role_id_map = {row[1]: row[0] for row in roles_result}

        # Get permission IDs
        perms_result = connection.execute(
            sa.text("SELECT id, scope FROM permissions")
        ).fetchall()
        perm_id_map = {row[1]: row[0] for row in perms_result}

        # Insert role-permission mappings
        for role_name, scopes in ROLE_PERMISSIONS.items():
            role_id = role_id_map.get(role_name)
            if role_id:
                for scope in scopes:
                    perm_id = perm_id_map.get(scope)
                    if perm_id:
                        connection.execute(
                            role_permissions_table.insert().values(
                                role_id=role_id,
                                permission_id=perm_id,
                                created_at=now,
                            )
                        )


def downgrade() -> None:
    """Remove seeded data (be careful - this deletes all role_permissions, roles, permissions)."""
    connection = op.get_bind()

    # Only delete system roles and their mappings, preserve user-created ones
    connection.execute(
        sa.text("""
            DELETE FROM role_permissions
            WHERE role_id IN (SELECT id FROM roles WHERE is_system = true)
        """)
    )

    connection.execute(
        sa.text("DELETE FROM roles WHERE is_system = true")
    )

    # Delete default permissions (by scope prefix)
    default_scopes = [p[0] for p in DEFAULT_PERMISSIONS]
    for scope in default_scopes:
        connection.execute(
            sa.text("DELETE FROM permissions WHERE scope = :scope"),
            {"scope": scope}
        )
