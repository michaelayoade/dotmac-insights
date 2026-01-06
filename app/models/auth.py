"""Authentication and Authorization models for RBAC.

This module defines the database models for:
- Users: Linked to better-auth via external_id
- Roles: Named permission bundles with optional hierarchy
- Permissions: Individual scope grants with categories
- ServiceTokens: Machine-to-machine authentication
- Groups: Team-based permission inheritance
- UserPermissions: Direct allow/deny grants
- UserSessions: Active session tracking
- RBACAuditLog: Permission change audit trail
"""

from __future__ import annotations

from sqlalchemy import String, Boolean, ForeignKey, Text, UniqueConstraint, Index, CheckConstraint, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from app.database import Base
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.models.contact_list import ContactList
    from app.models.party import Party
    from app.models.user_preference import UserPreference


class User(Base):
    """Application user linked to better-auth provider.

    Users are created on first JWT verification by matching the `sub` claim
    to external_id. The email comes from the JWT token claims.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External identity (better-auth user ID from JWT sub claim)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # User info (synced from JWT claims)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    picture: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Identity link
    party_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    party: Mapped[Optional["Party"]] = relationship(foreign_keys=[party_id])
    roles: Mapped[List["UserRole"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[UserRole.user_id]"
    )
    service_tokens: Mapped[List["ServiceToken"]] = relationship(
        back_populates="created_by_user",
        foreign_keys="[ServiceToken.created_by_id]"
    )
    contact_lists: Mapped[List["ContactList"]] = relationship(
        back_populates="owner",
        foreign_keys="[ContactList.owner_id]"
    )
    # Granular RBAC relationships
    direct_permissions: Mapped[List["UserPermission"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[UserPermission.user_id]"
    )
    group_memberships: Mapped[List["GroupMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[GroupMember.user_id]"
    )
    sessions: Mapped[List["UserSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[UserSession.user_id]"
    )
    # User preferences (one-to-one)
    preference: Mapped[Optional["UserPreference"]] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    @property
    def role_names(self) -> List[str]:
        """Get list of role names for this user."""
        return [ur.role.name for ur in self.roles if ur.role]

    @property
    def all_permissions(self) -> set[str]:
        """Get all permission scopes for this user across all roles."""
        if self.is_superuser:
            return {"*"}  # Superuser has all permissions

        permissions = set()
        for user_role in self.roles:
            if user_role.role:
                for role_perm in user_role.role.permissions:
                    if role_perm.permission:
                        permissions.add(role_perm.permission.scope)
        return permissions

    def has_permission(self, scope: str) -> bool:
        """Check if user has a specific permission scope."""
        if not self.is_active:
            return False
        if self.is_superuser:
            return True

        all_perms = self.all_permissions

        # Check exact match
        if scope in all_perms:
            return True

        # Check wildcard permissions (e.g., "sync:*" grants "sync:splynx:read")
        for perm in all_perms:
            if perm.endswith(":*"):
                prefix = perm[:-1]  # Remove the '*'
                if scope.startswith(prefix):
                    return True

        return False


class Role(Base):
    """Named role with associated permissions.

    Default roles:
    - admin: Full system access
    - analyst: Read-only access to analytics and explorer
    - operator: Sync and explorer access
    - viewer: Read-only explorer access

    Hierarchy support:
    - Roles can have a parent_role_id for inheritance
    - When inherit_permissions=True, role inherits all parent permissions
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Whether this is a system role (cannot be deleted)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    # Hierarchy support (granular RBAC)
    parent_role_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("roles.id"), nullable=True, index=True
    )
    inherit_permissions: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(default=0)  # Higher = checked first

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users: Mapped[List["UserRole"]] = relationship(back_populates="role", cascade="all, delete-orphan")
    permissions: Mapped[List["RolePermission"]] = relationship(back_populates="role", cascade="all, delete-orphan")
    parent: Mapped[Optional["Role"]] = relationship(
        "Role", remote_side="Role.id", foreign_keys=[parent_role_id], back_populates="children"
    )
    children: Mapped[List["Role"]] = relationship(
        "Role", back_populates="parent", foreign_keys=[parent_role_id]
    )
    group_roles: Mapped[List["GroupRole"]] = relationship(back_populates="role", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"

    @property
    def permission_scopes(self) -> List[str]:
        """Get list of permission scopes for this role."""
        return [rp.permission.scope for rp in self.permissions if rp.permission]

    def get_all_permission_scopes(self) -> set[str]:
        """Get all permission scopes including inherited from parent roles."""
        scopes = set(self.permission_scopes)
        if self.inherit_permissions and self.parent:
            scopes.update(self.parent.get_all_permission_scopes())
        return scopes


class Permission(Base):
    """Individual permission scope.

    Scope format: resource:action or resource:sub-resource:action
    Examples:
    - sync:splynx:write - Can trigger Splynx syncs
    - sync:splynx:read - Can view Splynx sync status
    - explorer:read - Can read data explorer
    - analytics:read - Can view analytics
    - admin:users:write - Can manage users
    - admin:roles:write - Can manage roles
    """

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Scope identifier (e.g., "sync:splynx:write")
    scope: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

    # Human-readable description
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Category for grouping in UI (legacy string field)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Enhanced category reference (granular RBAC)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("permission_categories.id"), nullable=True, index=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_order: Mapped[int] = mapped_column(default=0)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    roles: Mapped[List["RolePermission"]] = relationship(back_populates="permission", cascade="all, delete-orphan")
    category_rel: Mapped[Optional["PermissionCategory"]] = relationship(back_populates="permissions")
    user_permissions: Mapped[List["UserPermission"]] = relationship(
        back_populates="permission", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Permission {self.scope}>"


class UserRole(Base):
    """Junction table for User-Role many-to-many relationship."""

    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), index=True)

    # When role was assigned
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Who assigned the role (for audit trail)
    assigned_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[user_id], back_populates="roles")
    role: Mapped["Role"] = relationship(back_populates="users")
    assigned_by: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_by_id])

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )


class RolePermission(Base):
    """Junction table for Role-Permission many-to-many relationship."""

    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), index=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    role: Mapped["Role"] = relationship(back_populates="permissions")
    permission: Mapped["Permission"] = relationship(back_populates="roles")

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )


class ServiceToken(Base):
    """Service token for machine-to-machine authentication.

    Service tokens are used by external systems, scripts, or services
    to authenticate with the API. They have associated scopes and can
    be revoked independently.
    """

    __tablename__ = "service_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Token identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Token prefix for identification (first 8 chars of token)
    # Stored for easy identification without exposing full token
    token_prefix: Mapped[str] = mapped_column(String(12), index=True, nullable=False)

    # Hashed token (bcrypt or similar)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Scopes as comma-separated string (e.g., "sync:splynx:write,explorer:read")
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Expiration (null = never expires)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)

    # Usage tracking
    last_used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    use_count: Mapped[int] = mapped_column(default=0)

    # Audit trail
    # nullable=True with SET NULL on user deletion - preserves token if creator deleted
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    revoked_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    created_by_user: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_id], back_populates="service_tokens"
    )
    revoked_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[revoked_by_id])

    __table_args__ = (
        Index("ix_service_tokens_active_expires", "is_active", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<ServiceToken {self.name} ({self.token_prefix}...)>"

    @property
    def scope_list(self) -> List[str]:
        """Get list of scopes from comma-separated string."""
        if not self.scopes:
            return []
        return [s.strip() for s in self.scopes.split(",") if s.strip()]

    @scope_list.setter
    def scope_list(self, scopes: List[str]) -> None:
        """Set scopes from list."""
        self.scopes = ",".join(scopes)

    def has_scope(self, scope: str) -> bool:
        """Check if token has a specific scope."""
        if not self.is_active:
            return False

        # Check expiration
        if self.expires_at and utc_now() > self.expires_at:
            return False

        token_scopes = self.scope_list

        # Check exact match
        if scope in token_scopes:
            return True

        # Check wildcard
        for ts in token_scopes:
            if ts.endswith(":*"):
                prefix = ts[:-1]
                if scope.startswith(prefix):
                    return True

        return False

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.expires_at is None:
            return False
        return utc_now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is active and not expired."""
        return self.is_active and not self.is_expired and self.revoked_at is None


class TokenDenylist(Base):
    """Denylist for revoked JWT tokens.

    When a user is disabled or their roles change, their JWT tokens
    are added to this denylist until they expire naturally.
    This is checked on every request for denylisted tokens.
    """

    __tablename__ = "token_denylist"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # JWT ID (jti claim) or token hash
    jti: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # When the token expires (for cleanup)
    expires_at: Mapped[datetime] = mapped_column(index=True, nullable=False)

    # When added to denylist
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Reason for denylisting
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<TokenDenylist {self.jti[:12]}...>"


# =============================================================================
# GRANULAR RBAC MODELS
# =============================================================================


class PermissionCategory(Base):
    """Category for organizing permissions in the UI.

    Categories group related permissions together for easier management.
    Each category has an icon and display order for UI presentation.
    """

    __tablename__ = "permission_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    display_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    permissions: Mapped[List["Permission"]] = relationship(back_populates="category_rel")

    def __repr__(self) -> str:
        return f"<PermissionCategory {self.name}>"


class Group(Base):
    """Group for team-based permission assignment.

    Groups allow assigning roles to teams of users. When a user is a member
    of a group, they inherit all roles (and their permissions) assigned to
    that group.
    """

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    members: Mapped[List["GroupMember"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    roles: Mapped[List["GroupRole"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    created_by: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by_id])

    def __repr__(self) -> str:
        return f"<Group {self.name}>"

    @property
    def member_count(self) -> int:
        """Get the number of members in this group."""
        return len(self.members)

    @property
    def role_names(self) -> List[str]:
        """Get list of role names assigned to this group."""
        return [gr.role.name for gr in self.roles if gr.role]


class GroupMember(Base):
    """Junction table for Group-User membership."""

    __tablename__ = "group_members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    added_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    group: Mapped["Group"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(foreign_keys=[user_id], back_populates="group_memberships")
    added_by: Mapped[Optional["User"]] = relationship(foreign_keys=[added_by_id])

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_member"),
    )


class GroupRole(Base):
    """Junction table for Group-Role assignment."""

    __tablename__ = "group_roles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    assigned_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    group: Mapped["Group"] = relationship(back_populates="roles")
    role: Mapped["Role"] = relationship(back_populates="group_roles")
    assigned_by: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_by_id])

    __table_args__ = (
        UniqueConstraint("group_id", "role_id", name="uq_group_role"),
    )


class UserPermission(Base):
    """Direct permission grant or denial for a user.

    Allows granting or denying specific permissions to a user without
    going through roles. Useful for exceptions and temporary access.

    Grant types:
    - 'allow': Explicitly grants the permission
    - 'deny': Explicitly denies the permission (takes precedence)

    Conditions can be JSON objects specifying when the permission applies,
    e.g., {"own_only": true} or {"department_id": [1, 2, 3]}.
    """

    __tablename__ = "user_permissions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    grant_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'allow' or 'deny'
    conditions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[user_id], back_populates="direct_permissions")
    permission: Mapped["Permission"] = relationship(back_populates="user_permissions")
    created_by: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by_id])

    __table_args__ = (
        UniqueConstraint("user_id", "permission_id", name="uq_user_permission"),
        CheckConstraint("grant_type IN ('allow', 'deny')", name="ck_user_permissions_grant_type"),
        Index("ix_user_permissions_validity", "valid_from", "valid_until"),
    )

    @property
    def is_valid(self) -> bool:
        """Check if the permission grant is currently valid."""
        now = utc_now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True

    @property
    def is_allow(self) -> bool:
        """Check if this is an allow grant."""
        return self.grant_type == "allow"

    @property
    def is_deny(self) -> bool:
        """Check if this is a deny grant."""
        return self.grant_type == "deny"


class UserSession(Base):
    """Active user session tracking.

    Tracks user sessions for security monitoring, allowing users to see
    their active sessions and revoke them if needed.
    """

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    device_info: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    revoked_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    revoke_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[user_id], back_populates="sessions")
    revoked_by: Mapped[Optional["User"]] = relationship(foreign_keys=[revoked_by_id])

    __table_args__ = (
        Index("ix_user_sessions_user_active", "user_id", "is_active"),
        Index("ix_user_sessions_expires", "expires_at"),
    )

    @property
    def is_valid(self) -> bool:
        """Check if the session is still valid."""
        if not self.is_active:
            return False
        if self.revoked_at:
            return False
        if utc_now() > self.expires_at:
            return False
        return True


class RBACAuditLog(Base):
    """Immutable audit log for RBAC changes.

    Records all changes to roles, permissions, groups, and user assignments
    for compliance and security monitoring.
    """

    __tablename__ = "rbac_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)
    target_entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_entity_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    old_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_rbac_audit_log_entity", "entity_type", "entity_id"),
    )

    def __repr__(self) -> str:
        return f"<RBACAuditLog {self.action} {self.entity_type}:{self.entity_id}>"
