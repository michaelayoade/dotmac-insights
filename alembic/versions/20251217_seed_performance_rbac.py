"""Seed performance module RBAC scopes (consolidated)

Adds all RBAC permissions required by the performance management module:
- performance:read   - View KPIs, KRAs, scorecards, analytics
- performance:write  - Create/edit definitions, templates, submit scores
- performance:admin  - Period lifecycle, scorecard generation, finalization
- performance:self   - View own performance scorecards
- performance:team   - View team performance data (managers)
- performance:review - Review, approve, and override scorecards

Creates new role:
- hr_manager - Full performance management access

Maps permissions to roles:
- admin:      read, write, admin, self, team, review
- operator:   read, write, self, team, review
- analyst:    read, self
- viewer:     read, self
- hr_manager: read, write, admin, self, team, review

Revision ID: perf002_seed_rbac
Revises: merge_uc003_perf001
Create Date: 2025-12-17
"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa
from datetime import datetime


revision: str = "perf002_seed_rbac"
down_revision: Union[str, None] = "merge_uc003_perf001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All performance permissions required by routers
PERFORMANCE_PERMISSIONS = [
    ("performance:read", "View performance data (KPIs, KRAs, scorecards, analytics)", "performance"),
    ("performance:write", "Create and update KPI/KRA definitions, templates, bindings, submit scores", "performance"),
    ("performance:admin", "Full performance admin (period lifecycle, scorecard generation, finalization)", "performance"),
    ("performance:self", "View own performance scorecards and data", "performance"),
    ("performance:team", "View team performance data (managers)", "performance"),
    ("performance:review", "Review, approve, and override scorecards", "performance"),
]

# New roles for performance management
NEW_ROLES = [
    ("hr_manager", "HR Manager - full access to performance management and employee data", True),
]

# Role permission assignments
ROLE_PERFORMANCE_PERMISSIONS = {
    "admin": [
        "performance:read", "performance:write", "performance:admin",
        "performance:self", "performance:team", "performance:review",
    ],
    "operator": [
        "performance:read", "performance:write",
        "performance:self", "performance:team", "performance:review",
    ],
    "analyst": [
        "performance:read", "performance:self",
    ],
    "viewer": [
        "performance:read", "performance:self",
    ],
    "hr_manager": [
        "performance:read", "performance:write", "performance:admin",
        "performance:self", "performance:team", "performance:review",
    ],
}


def upgrade() -> None:
    """Seed performance permissions and role mappings."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    now = datetime.utcnow()

    # =========================================================================
    # STEP 1: Insert performance permissions
    # =========================================================================
    for scope, description, category in PERFORMANCE_PERMISSIONS:
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

    # =========================================================================
    # STEP 2: Create HR Manager role if it doesn't exist
    # =========================================================================
    for name, description, is_system in NEW_ROLES:
        connection.execute(
            sa.text("""
                INSERT INTO roles (name, description, is_system, created_at, updated_at)
                VALUES (:name, :description, :is_system, :created_at, :updated_at)
                ON CONFLICT (name) DO UPDATE SET
                    description = EXCLUDED.description
            """),
            {
                "name": name,
                "description": description,
                "is_system": is_system,
                "created_at": now,
                "updated_at": now,
            }
        )

    # =========================================================================
    # STEP 3: Create role-permission mappings
    # =========================================================================

    # Get all role IDs
    roles_result = connection.execute(
        sa.text("SELECT id, name FROM roles")
    ).fetchall()
    role_id_map = {row[1]: row[0] for row in roles_result}

    # Get all permission IDs
    perms_result = connection.execute(
        sa.text("SELECT id, scope FROM permissions WHERE scope LIKE 'performance:%'")
    ).fetchall()
    perm_id_map = {row[1]: row[0] for row in perms_result}

    # Assign permissions to roles
    for role_name, scopes in ROLE_PERFORMANCE_PERMISSIONS.items():
        role_id = role_id_map.get(role_name)
        if not role_id:
            continue

        for scope in scopes:
            perm_id = perm_id_map.get(scope)
            if not perm_id:
                continue

            # Insert if not exists
            connection.execute(
                sa.text("""
                    INSERT INTO role_permissions (role_id, permission_id, created_at)
                    VALUES (:role_id, :perm_id, :created_at)
                    ON CONFLICT DO NOTHING
                """),
                {"role_id": role_id, "perm_id": perm_id, "created_at": now}
            )


def downgrade() -> None:
    """Remove performance permissions and role mappings."""
    if context.is_offline_mode():
        return

    connection = op.get_bind()
    if connection is None:
        return

    # Get permission IDs for performance scopes
    perms_result = connection.execute(
        sa.text("SELECT id FROM permissions WHERE scope LIKE 'performance:%'")
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

    # Remove HR Manager role
    connection.execute(
        sa.text("DELETE FROM roles WHERE name = 'hr_manager' AND is_system = true")
    )
