"""RBAC Service - Permission resolution with caching and auditing.

This service handles granular permission resolution including:
- Direct user permissions (allow/deny)
- Role-based permissions (with hierarchy)
- Group-based permissions
- Conditional permissions

Permission resolution order (DENY wins):
1. Direct user DENY permissions (highest priority)
2. Direct user ALLOW permissions
3. Role permissions (with hierarchy resolution)
4. Group role permissions
5. Default: DENY
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import structlog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.feature_flags import feature_flags
from app.models.auth import (
    Group,
    GroupMember,
    GroupRole,
    Permission,
    RBACAuditLog,
    Role,
    RolePermission,
    User,
    UserPermission,
    UserRole,
)
from app.utils.datetime_utils import utc_now

logger = structlog.get_logger()


class EffectivePermissions(BaseModel):
    """Represents the resolved effective permissions for a user."""

    allowed_scopes: set[str] = field(default_factory=set)
    denied_scopes: set[str] = field(default_factory=set)
    conditional_permissions: dict[str, dict] = field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    def model_dump_json(self) -> str:
        """Serialize to JSON for caching."""
        return json.dumps({
            "allowed_scopes": list(self.allowed_scopes),
            "denied_scopes": list(self.denied_scopes),
            "conditional_permissions": self.conditional_permissions,
        })

    @classmethod
    def model_validate_json(cls, data: str) -> "EffectivePermissions":
        """Deserialize from JSON cache."""
        parsed = json.loads(data)
        return cls(
            allowed_scopes=set(parsed.get("allowed_scopes", [])),
            denied_scopes=set(parsed.get("denied_scopes", [])),
            conditional_permissions=parsed.get("conditional_permissions", {}),
        )


@dataclass
class PermissionGrant:
    """Represents a single permission grant with metadata."""

    scope: str
    grant_type: str  # 'allow' or 'deny'
    source: str  # 'direct', 'role', 'group'
    source_name: str  # Role or group name
    conditions: Optional[dict] = None
    priority: int = 0


class RBACService:
    """Service for resolving and managing RBAC permissions."""

    def __init__(self, db: Session):
        self.db = db

    async def get_effective_permissions(
        self,
        user_id: int,
        bypass_cache: bool = False,
    ) -> EffectivePermissions:
        """
        Resolve all effective permissions for a user.

        Args:
            user_id: The user to resolve permissions for
            bypass_cache: Skip Redis cache lookup

        Returns:
            EffectivePermissions containing allowed, denied, and conditional scopes
        """
        # Try cache first if enabled
        if feature_flags.RBAC_CACHE_ENABLED and not bypass_cache:
            cached = await self._get_cached_permissions(user_id)
            if cached:
                return cached

        # Get user with relationships
        user = self.db.query(User).options(
            joinedload(User.roles).joinedload(UserRole.role).joinedload(Role.permissions).joinedload(RolePermission.permission),
            joinedload(User.direct_permissions).joinedload(UserPermission.permission),
            joinedload(User.group_memberships).joinedload(GroupMember.group).joinedload(Group.roles).joinedload(GroupRole.role),
        ).filter(User.id == user_id).first()

        if not user:
            return EffectivePermissions()

        # Collect all grants
        grants: list[PermissionGrant] = []

        # 1. Direct user permissions (highest priority)
        if feature_flags.RBAC_DIRECT_PERMISSIONS_ENABLED:
            grants.extend(self._get_direct_permission_grants(user))

        # 2. Role permissions (with hierarchy)
        grants.extend(self._get_role_permission_grants(user))

        # 3. Group role permissions
        if feature_flags.RBAC_GROUPS_ENABLED:
            grants.extend(self._get_group_permission_grants(user))

        # Merge grants with DENY taking precedence
        effective = self._merge_permission_grants(grants)

        # Cache result
        if feature_flags.RBAC_CACHE_ENABLED:
            await self._cache_permissions(user_id, effective)

        return effective

    def _get_direct_permission_grants(self, user: User) -> list[PermissionGrant]:
        """Get direct user permission grants (allow/deny)."""
        grants = []
        now = utc_now()

        for up in user.direct_permissions:
            # Check validity
            if up.valid_from and now < up.valid_from:
                continue
            if up.valid_until and now > up.valid_until:
                continue

            grants.append(PermissionGrant(
                scope=up.permission.scope,
                grant_type=up.grant_type,
                source="direct",
                source_name="user",
                conditions=up.conditions,
                priority=100,  # Highest priority
            ))

        return grants

    def _get_role_permission_grants(self, user: User) -> list[PermissionGrant]:
        """Get role-based permission grants (with optional hierarchy)."""
        grants = []
        seen_roles: set[int] = set()

        for user_role in user.roles:
            role = user_role.role
            if not role or role.id in seen_roles:
                continue

            # Collect permissions from this role
            role_scopes = self._resolve_role_permissions(role, seen_roles)

            for scope in role_scopes:
                grants.append(PermissionGrant(
                    scope=scope,
                    grant_type="allow",
                    source="role",
                    source_name=role.name,
                    priority=role.priority,
                ))

        return grants

    def _resolve_role_permissions(self, role: Role, seen: set[int]) -> set[str]:
        """Resolve permissions for a role, including inherited permissions."""
        if role.id in seen:
            return set()

        seen.add(role.id)
        scopes = set()

        # Add this role's direct permissions
        for rp in role.permissions:
            if rp.permission:
                scopes.add(rp.permission.scope)

        # Add inherited permissions from parent
        if feature_flags.RBAC_ROLE_HIERARCHY_ENABLED and role.inherit_permissions and role.parent:
            scopes.update(self._resolve_role_permissions(role.parent, seen))

        return scopes

    def _get_group_permission_grants(self, user: User) -> list[PermissionGrant]:
        """Get group-based permission grants."""
        grants = []
        seen_roles: set[int] = set()

        for membership in user.group_memberships:
            group = membership.group
            if not group or not group.is_active:
                continue

            for group_role in group.roles:
                role = group_role.role
                if not role or role.id in seen_roles:
                    continue

                role_scopes = self._resolve_role_permissions(role, seen_roles)

                for scope in role_scopes:
                    grants.append(PermissionGrant(
                        scope=scope,
                        grant_type="allow",
                        source="group",
                        source_name=f"{group.name}:{role.name}",
                        priority=role.priority - 10,  # Slightly lower than direct role
                    ))

        return grants

    def _merge_permission_grants(self, grants: list[PermissionGrant]) -> EffectivePermissions:
        """Merge permission grants with DENY taking precedence."""
        allowed: set[str] = set()
        denied: set[str] = set()
        conditions: dict[str, dict] = {}

        # Sort by priority (higher first)
        sorted_grants = sorted(grants, key=lambda g: g.priority, reverse=True)

        for grant in sorted_grants:
            if grant.grant_type == "deny":
                denied.add(grant.scope)
                # Remove from allowed if previously added
                allowed.discard(grant.scope)
            elif grant.grant_type == "allow":
                # Only add if not denied
                if grant.scope not in denied:
                    allowed.add(grant.scope)
                    if grant.conditions:
                        conditions[grant.scope] = grant.conditions

        return EffectivePermissions(
            allowed_scopes=allowed,
            denied_scopes=denied,
            conditional_permissions=conditions,
        )

    def has_permission(
        self,
        user_id: int,
        scope: str,
        context: Optional[dict] = None,
    ) -> bool:
        """
        Check if a user has a specific permission.

        Args:
            user_id: User to check
            scope: Permission scope (e.g., "customers:write")
            context: Optional context for conditional evaluation

        Returns:
            True if user has the permission
        """
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        if not user.is_active:
            return False

        if user.is_superuser:
            return True

        # For now, use synchronous check (async version available via get_effective_permissions)
        # This is a simplified check for common cases
        return self._check_permission_sync(user, scope, context)

    def _check_permission_sync(
        self,
        user: User,
        scope: str,
        context: Optional[dict] = None,
    ) -> bool:
        """Synchronous permission check for common cases."""
        # Check direct denies first
        if feature_flags.RBAC_DIRECT_PERMISSIONS_ENABLED:
            for up in user.direct_permissions:
                if up.is_valid and up.is_deny and self._scope_matches(up.permission.scope, scope):
                    return False

        # Check direct allows
        if feature_flags.RBAC_DIRECT_PERMISSIONS_ENABLED:
            for up in user.direct_permissions:
                if up.is_valid and up.is_allow and self._scope_matches(up.permission.scope, scope):
                    if up.conditions and context:
                        # Conditional check would go here
                        pass
                    return True

        # Check role permissions
        all_perms = user.all_permissions
        if scope in all_perms:
            return True

        # Check wildcard
        for perm in all_perms:
            if perm.endswith(":*"):
                prefix = perm[:-1]
                if scope.startswith(prefix):
                    return True

        return False

    def _scope_matches(self, pattern: str, scope: str) -> bool:
        """Check if a scope pattern matches a specific scope."""
        if pattern == scope:
            return True
        if pattern == "*":
            return True
        if pattern.endswith(":*"):
            prefix = pattern[:-1]
            return scope.startswith(prefix)
        return False

    async def _get_cached_permissions(self, user_id: int) -> Optional[EffectivePermissions]:
        """Get cached permissions from Redis."""
        try:
            from app.cache import get_redis_client
            client = await get_redis_client()
            if not client:
                return None

            key = f"rbac:user:{user_id}:permissions"
            data = await client.get(key)
            if data:
                return EffectivePermissions.model_validate_json(data)
        except Exception as e:
            logger.warning("rbac_cache_get_error", user_id=user_id, error=str(e))

        return None

    async def _cache_permissions(self, user_id: int, permissions: EffectivePermissions) -> None:
        """Cache permissions in Redis."""
        try:
            from app.cache import get_redis_client
            client = await get_redis_client()
            if not client:
                return

            key = f"rbac:user:{user_id}:permissions"
            await client.setex(
                key,
                feature_flags.RBAC_CACHE_TTL,
                permissions.model_dump_json(),
            )
        except Exception as e:
            logger.warning("rbac_cache_set_error", user_id=user_id, error=str(e))

    async def invalidate_user_cache(self, user_id: int) -> None:
        """Invalidate permission cache for a user."""
        try:
            from app.cache import get_redis_client
            client = await get_redis_client()
            if not client:
                return

            key = f"rbac:user:{user_id}:permissions"
            await client.delete(key)
            logger.info("rbac_cache_invalidated", user_id=user_id)
        except Exception as e:
            logger.warning("rbac_cache_invalidate_error", user_id=user_id, error=str(e))

    async def invalidate_role_cache(self, role_id: int) -> None:
        """Invalidate cache for all users with a specific role."""
        # Get all users with this role
        user_ids = self.db.execute(
            select(UserRole.user_id).where(UserRole.role_id == role_id)
        ).scalars().all()

        for user_id in user_ids:
            await self.invalidate_user_cache(user_id)

    async def invalidate_group_cache(self, group_id: int) -> None:
        """Invalidate cache for all users in a group."""
        user_ids = self.db.execute(
            select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        ).scalars().all()

        for user_id in user_ids:
            await self.invalidate_user_cache(user_id)

    # =========================================================================
    # AUDIT LOGGING
    # =========================================================================

    def log_rbac_change(
        self,
        action: str,
        entity_type: str,
        entity_id: int,
        target_entity_type: Optional[str] = None,
        target_entity_id: Optional[int] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> RBACAuditLog:
        """Log an RBAC change for audit purposes."""
        entry = RBACAuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            old_values=old_values,
            new_values=new_values,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
        )
        self.db.add(entry)
        self.db.flush()

        logger.info(
            "rbac_change",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            user_id=user_id,
        )

        return entry

    # =========================================================================
    # PERMISSION MANAGEMENT
    # =========================================================================

    def grant_direct_permission(
        self,
        user_id: int,
        permission_id: int,
        grant_type: str = "allow",
        conditions: Optional[dict] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        reason: Optional[str] = None,
        granted_by_id: Optional[int] = None,
        granted_by_email: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> UserPermission:
        """Grant a direct permission to a user."""
        # Check if already exists
        existing = self.db.query(UserPermission).filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_id == permission_id,
        ).first()

        if existing:
            # Update existing
            old_values = {
                "grant_type": existing.grant_type,
                "conditions": existing.conditions,
            }
            existing.grant_type = grant_type
            existing.conditions = conditions
            existing.valid_from = valid_from
            existing.valid_until = valid_until
            existing.reason = reason

            self.log_rbac_change(
                action="permission_updated",
                entity_type="user",
                entity_id=user_id,
                target_entity_type="permission",
                target_entity_id=permission_id,
                old_values=old_values,
                new_values={"grant_type": grant_type, "conditions": conditions},
                user_id=granted_by_id,
                user_email=granted_by_email,
                ip_address=ip_address,
            )

            return existing

        # Create new
        user_perm = UserPermission(
            user_id=user_id,
            permission_id=permission_id,
            grant_type=grant_type,
            conditions=conditions,
            valid_from=valid_from,
            valid_until=valid_until,
            reason=reason,
            created_by_id=granted_by_id,
        )
        self.db.add(user_perm)
        self.db.flush()

        self.log_rbac_change(
            action="permission_granted",
            entity_type="user",
            entity_id=user_id,
            target_entity_type="permission",
            target_entity_id=permission_id,
            new_values={"grant_type": grant_type, "conditions": conditions},
            user_id=granted_by_id,
            user_email=granted_by_email,
            ip_address=ip_address,
        )

        return user_perm

    def revoke_direct_permission(
        self,
        user_id: int,
        permission_id: int,
        revoked_by_id: Optional[int] = None,
        revoked_by_email: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """Revoke a direct permission from a user."""
        user_perm = self.db.query(UserPermission).filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_id == permission_id,
        ).first()

        if not user_perm:
            return False

        old_values = {
            "grant_type": user_perm.grant_type,
            "conditions": user_perm.conditions,
        }

        self.db.delete(user_perm)

        self.log_rbac_change(
            action="permission_revoked",
            entity_type="user",
            entity_id=user_id,
            target_entity_type="permission",
            target_entity_id=permission_id,
            old_values=old_values,
            user_id=revoked_by_id,
            user_email=revoked_by_email,
            ip_address=ip_address,
        )

        return True

    # =========================================================================
    # GROUP MANAGEMENT
    # =========================================================================

    def add_user_to_group(
        self,
        user_id: int,
        group_id: int,
        added_by_id: Optional[int] = None,
        added_by_email: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> GroupMember:
        """Add a user to a group."""
        # Check if already member
        existing = self.db.query(GroupMember).filter(
            GroupMember.user_id == user_id,
            GroupMember.group_id == group_id,
        ).first()

        if existing:
            return existing

        member = GroupMember(
            user_id=user_id,
            group_id=group_id,
            added_by_id=added_by_id,
        )
        self.db.add(member)
        self.db.flush()

        self.log_rbac_change(
            action="group_member_added",
            entity_type="group",
            entity_id=group_id,
            target_entity_type="user",
            target_entity_id=user_id,
            user_id=added_by_id,
            user_email=added_by_email,
            ip_address=ip_address,
        )

        return member

    def remove_user_from_group(
        self,
        user_id: int,
        group_id: int,
        removed_by_id: Optional[int] = None,
        removed_by_email: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """Remove a user from a group."""
        member = self.db.query(GroupMember).filter(
            GroupMember.user_id == user_id,
            GroupMember.group_id == group_id,
        ).first()

        if not member:
            return False

        self.db.delete(member)

        self.log_rbac_change(
            action="group_member_removed",
            entity_type="group",
            entity_id=group_id,
            target_entity_type="user",
            target_entity_id=user_id,
            user_id=removed_by_id,
            user_email=removed_by_email,
            ip_address=ip_address,
        )

        return True

    def assign_role_to_group(
        self,
        group_id: int,
        role_id: int,
        assigned_by_id: Optional[int] = None,
        assigned_by_email: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> GroupRole:
        """Assign a role to a group."""
        existing = self.db.query(GroupRole).filter(
            GroupRole.group_id == group_id,
            GroupRole.role_id == role_id,
        ).first()

        if existing:
            return existing

        group_role = GroupRole(
            group_id=group_id,
            role_id=role_id,
            assigned_by_id=assigned_by_id,
        )
        self.db.add(group_role)
        self.db.flush()

        self.log_rbac_change(
            action="group_role_assigned",
            entity_type="group",
            entity_id=group_id,
            target_entity_type="role",
            target_entity_id=role_id,
            user_id=assigned_by_id,
            user_email=assigned_by_email,
            ip_address=ip_address,
        )

        return group_role

    def unassign_role_from_group(
        self,
        group_id: int,
        role_id: int,
        removed_by_id: Optional[int] = None,
        removed_by_email: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """Remove a role from a group."""
        group_role = self.db.query(GroupRole).filter(
            GroupRole.group_id == group_id,
            GroupRole.role_id == role_id,
        ).first()

        if not group_role:
            return False

        self.db.delete(group_role)

        self.log_rbac_change(
            action="group_role_removed",
            entity_type="group",
            entity_id=group_id,
            target_entity_type="role",
            target_entity_id=role_id,
            user_id=removed_by_id,
            user_email=removed_by_email,
            ip_address=ip_address,
        )

        return True
