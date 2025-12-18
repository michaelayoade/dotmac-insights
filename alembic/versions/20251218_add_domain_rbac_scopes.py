"""add_domain_rbac_scopes

Revision ID: 20251218_add_domain_rbac_scopes
Revises: 20251217_add_crm_project_kpis
Create Date: 2025-12-18

Adds RBAC scopes for domain modules as per Phase 1 of Security plan:
- contacts:read - View contacts and customers
- contacts:write - Create, update, delete contacts
- contacts:export - Export contact data
- tickets:read - View support tickets
- tickets:write - Create, update tickets
- billing:read - View invoices and payments
- billing:write - Create, update invoices and payments
"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = "20251218_add_domain_rbac_scopes"
down_revision: Union[str, None] = "20251217_add_crm_project_kpis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Domain permissions to add
NEW_PERMISSIONS = [
    # Contacts domain
    ("contacts:read", "View contacts and customers", "contacts"),
    ("contacts:write", "Create, update, delete contacts", "contacts"),
    ("contacts:export", "Export contact data", "contacts"),
    # Support/Tickets domain
    ("tickets:read", "View support tickets", "support"),
    ("tickets:write", "Create, update tickets", "support"),
    # Billing domain
    ("billing:read", "View invoices and payments", "billing"),
    ("billing:write", "Create, update invoices and payments", "billing"),
]


# Role assignments for new permissions
ROLE_PERMISSIONS = {
    "admin": [
        "contacts:read", "contacts:write", "contacts:export",
        "tickets:read", "tickets:write",
        "billing:read", "billing:write",
    ],
    "operator": [
        "contacts:read", "contacts:write",
        "tickets:read", "tickets:write",
        "billing:read",
    ],
    "analyst": [
        "contacts:read", "contacts:export",
        "tickets:read",
        "billing:read",
    ],
    "viewer": [
        "contacts:read",
        "tickets:read",
        "billing:read",
    ],
}


def upgrade() -> None:
    """Add domain RBAC permissions and assign to roles."""
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
    """Remove domain RBAC permissions."""
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
