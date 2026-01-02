"""Add granular RBAC schema

Extends the existing auth system with:
- Permission categories for UI organization
- Role hierarchy with inheritance
- Groups for team-based permissions
- Direct user permissions (allow/deny)
- Session tracking
- RBAC audit logging

Revision ID: rbac_granular_001
Revises: e12634e8e3aa
Create Date: 2026-01-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "rbac_granular_001"
down_revision: Union[str, None] = "e12634e8e3aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # NEW TABLE: permission_categories
    # =========================================================================
    op.create_table(
        "permission_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_permission_categories_name"),
    )
    op.create_index("ix_permission_categories_name", "permission_categories", ["name"])

    # =========================================================================
    # ALTER TABLE: permissions - add category_id and display fields
    # =========================================================================
    op.add_column("permissions", sa.Column("display_name", sa.String(255), nullable=True))
    op.add_column(
        "permissions",
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("permission_categories.id"), nullable=True),
    )
    op.add_column("permissions", sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("permissions", sa.Column("is_deprecated", sa.Boolean(), nullable=False, server_default="false"))
    op.create_index("ix_permissions_category_id", "permissions", ["category_id"])

    # =========================================================================
    # ALTER TABLE: roles - add hierarchy support
    # =========================================================================
    op.add_column(
        "roles",
        sa.Column("parent_role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=True),
    )
    op.add_column("roles", sa.Column("inherit_permissions", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("roles", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_roles_parent_role_id", "roles", ["parent_role_id"])

    # =========================================================================
    # NEW TABLE: groups
    # =========================================================================
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_groups_name"),
    )
    op.create_index("ix_groups_name", "groups", ["name"])
    op.create_index("ix_groups_is_active", "groups", ["is_active"])

    # =========================================================================
    # NEW TABLE: group_members
    # =========================================================================
    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("added_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_member"),
    )
    op.create_index("ix_group_members_group_id", "group_members", ["group_id"])
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"])

    # =========================================================================
    # NEW TABLE: group_roles
    # =========================================================================
    op.create_table(
        "group_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("assigned_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "role_id", name="uq_group_role"),
    )
    op.create_index("ix_group_roles_group_id", "group_roles", ["group_id"])
    op.create_index("ix_group_roles_role_id", "group_roles", ["role_id"])

    # =========================================================================
    # NEW TABLE: user_permissions (direct allow/deny)
    # =========================================================================
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grant_type", sa.String(10), nullable=False),  # 'allow' or 'deny'
        sa.Column("conditions", postgresql.JSONB(), nullable=True),
        sa.Column("valid_from", sa.DateTime(), nullable=True),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "permission_id", name="uq_user_permission"),
        sa.CheckConstraint("grant_type IN ('allow', 'deny')", name="ck_user_permissions_grant_type"),
    )
    op.create_index("ix_user_permissions_user_id", "user_permissions", ["user_id"])
    op.create_index("ix_user_permissions_permission_id", "user_permissions", ["permission_id"])
    op.create_index(
        "ix_user_permissions_validity",
        "user_permissions",
        ["valid_from", "valid_until"],
    )

    # =========================================================================
    # NEW TABLE: user_sessions
    # =========================================================================
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(255), nullable=False),  # JWT jti or session token
        sa.Column("device_info", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_activity_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoke_reason", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_user_sessions_session_id"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_session_id", "user_sessions", ["session_id"])
    op.create_index(
        "ix_user_sessions_user_active",
        "user_sessions",
        ["user_id", "is_active"],
    )
    op.create_index(
        "ix_user_sessions_expires",
        "user_sessions",
        ["expires_at"],
    )

    # =========================================================================
    # NEW TABLE: rbac_audit_log
    # =========================================================================
    op.create_table(
        "rbac_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action", sa.String(50), nullable=False),  # role_assigned, permission_changed, etc.
        sa.Column("entity_type", sa.String(50), nullable=False),  # user, role, group, permission
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("target_entity_type", sa.String(50), nullable=True),
        sa.Column("target_entity_id", sa.Integer(), nullable=True),
        sa.Column("old_values", postgresql.JSONB(), nullable=True),
        sa.Column("new_values", postgresql.JSONB(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),  # Who made the change
        sa.Column("user_email", sa.String(255), nullable=True),  # Denormalized for immutability
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rbac_audit_log_entity", "rbac_audit_log", ["entity_type", "entity_id"])
    op.create_index("ix_rbac_audit_log_created", "rbac_audit_log", ["created_at"])
    op.create_index("ix_rbac_audit_log_user", "rbac_audit_log", ["user_id"])
    op.create_index("ix_rbac_audit_log_action", "rbac_audit_log", ["action"])


def downgrade() -> None:
    # Drop new tables in reverse order
    op.drop_table("rbac_audit_log")
    op.drop_table("user_sessions")
    op.drop_table("user_permissions")
    op.drop_table("group_roles")
    op.drop_table("group_members")
    op.drop_table("groups")

    # Remove columns from roles
    op.drop_index("ix_roles_parent_role_id", table_name="roles")
    op.drop_column("roles", "priority")
    op.drop_column("roles", "inherit_permissions")
    op.drop_column("roles", "parent_role_id")

    # Remove columns from permissions
    op.drop_index("ix_permissions_category_id", table_name="permissions")
    op.drop_column("permissions", "is_deprecated")
    op.drop_column("permissions", "display_order")
    op.drop_column("permissions", "category_id")
    op.drop_column("permissions", "display_name")

    # Drop permission_categories
    op.drop_index("ix_permission_categories_name", table_name="permission_categories")
    op.drop_table("permission_categories")
