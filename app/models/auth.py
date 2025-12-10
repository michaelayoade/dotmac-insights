"""Authentication and Authorization models for RBAC.

This module defines the database models for:
- Users: Linked to better-auth via external_id
- Roles: Named permission bundles
- Permissions: Individual scope grants
- ServiceTokens: Machine-to-machine authentication
"""

from __future__ import annotations

from sqlalchemy import String, Boolean, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List
from app.database import Base


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

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    roles: Mapped[List["UserRole"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[UserRole.user_id]"
    )
    service_tokens: Mapped[List["ServiceToken"]] = relationship(
        back_populates="created_by_user",
        foreign_keys="[ServiceToken.created_by_id]"
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
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Whether this is a system role (cannot be deleted)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users: Mapped[List["UserRole"]] = relationship(back_populates="role", cascade="all, delete-orphan")
    permissions: Mapped[List["RolePermission"]] = relationship(back_populates="role", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"

    @property
    def permission_scopes(self) -> List[str]:
        """Get list of permission scopes for this role."""
        return [rp.permission.scope for rp in self.permissions if rp.permission]


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

    # Category for grouping in UI
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    roles: Mapped[List["RolePermission"]] = relationship(back_populates="permission", cascade="all, delete-orphan")

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
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    revoked_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    created_by_user: Mapped["User"] = relationship(foreign_keys=[created_by_id], back_populates="service_tokens")
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
        if self.expires_at and datetime.utcnow() > self.expires_at:
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
        return datetime.utcnow() > self.expires_at

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
