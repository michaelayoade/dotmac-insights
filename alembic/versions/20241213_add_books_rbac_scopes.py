"""add_books_rbac_scopes

Revision ID: 20241213_add_books_rbac_scopes
Revises: 20241213_accounting_books_infrastructure
Create Date: 2024-12-13

Adds RBAC scopes for accounting books module:
- books:read - View accounting data
- books:write - Create/update accounting documents
- books:approve - Approve documents
- books:close - Close/reopen fiscal periods
- books:admin - Full accounting admin (workflows, rates, controls)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = "20241213_add_books_rbac_scopes"
down_revision: Union[str, None] = "20241213_accounting_books_infrastructure"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Books permissions to add
BOOKS_PERMISSIONS = [
    ("books:read", "View accounting data (accounts, journals, GL)", "books"),
    ("books:write", "Create and update accounting documents (JE, accounts, suppliers)", "books"),
    ("books:approve", "Approve documents in approval workflows", "books"),
    ("books:close", "Close and reopen fiscal periods, generate closing entries", "books"),
    ("books:admin", "Full accounting admin (workflows, exchange rates, controls)", "books"),
]

# Role assignments for books permissions
ROLE_BOOKS_PERMISSIONS = {
    "admin": [
        "books:read", "books:write", "books:approve", "books:close", "books:admin",
    ],
    "operator": [
        "books:read", "books:write", "books:approve",
    ],
    "analyst": [
        "books:read",
    ],
    "viewer": [
        "books:read",
    ],
}


def upgrade() -> None:
    connection = op.get_bind()
    now = datetime.utcnow()

    # Insert new permissions
    for scope, description, category in BOOKS_PERMISSIONS:
        connection.execute(
            sa.text("""
                INSERT INTO permissions (scope, description, category, created_at)
                VALUES (:scope, :description, :category, :created_at)
                ON CONFLICT (scope) DO NOTHING
            """),
            {"scope": scope, "description": description, "category": category, "created_at": now}
        )

    # Get permission IDs
    perms_result = connection.execute(
        sa.text("SELECT id, scope FROM permissions WHERE scope LIKE 'books:%'")
    ).fetchall()
    perm_id_map = {row[1]: row[0] for row in perms_result}

    # Get role IDs
    roles_result = connection.execute(
        sa.text("SELECT id, name FROM roles WHERE name IN ('admin', 'operator', 'analyst', 'viewer')")
    ).fetchall()
    role_id_map = {row[1]: row[0] for row in roles_result}

    # Assign permissions to roles
    for role_name, scopes in ROLE_BOOKS_PERMISSIONS.items():
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
    connection = op.get_bind()

    # Get permission IDs for books scopes
    perms_result = connection.execute(
        sa.text("SELECT id FROM permissions WHERE scope LIKE 'books:%'")
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
