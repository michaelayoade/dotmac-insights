"""Service layer for settings admin operations."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import secrets as py_secrets
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.auth import (
    Group,
    GroupMember,
    GroupRole,
    Permission,
    PermissionCategory,
    Role,
    ServiceToken,
    User,
    UserPermission,
    UserSession,
)
from app.models.notification import WebhookConfig, WebhookDelivery
from app.models.activity_log import ActivityLog
from app.models.settings import SettingsAuditLog
from app.utils.datetime_utils import utc_now
from app.services.session_service import SessionService
from app.services.activity_logger import ActivityLogger


class AdminSettingsService:
    """Service wrapper for settings admin data access."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Users
    # ------------------------------------------------------------------ #
    def list_users(
        self,
        q: Optional[str],
        status: Optional[str],
        page: int,
        per_page: int,
    ) -> tuple[list[User], int]:
        query = self.db.query(User)

        if q:
            search_filter = or_(
                User.email.ilike(f"%{q}%"),
                User.name.ilike(f"%{q}%"),
            )
            query = query.filter(search_filter)

        if status:
            query = query.filter(User.is_active == (status == "active"))

        total = query.count()
        users = query.order_by(User.email).offset((page - 1) * per_page).limit(per_page).all()
        return users, total

    def get_user(self, user_id: str | int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def update_user(
        self,
        user: User,
        *,
        is_active: Optional[bool] = None,
        role_ids: Optional[list[str]] = None,
        update_roles: bool = False,
    ) -> User:
        if is_active is not None:
            user.is_active = is_active

        if update_roles:
            roles: list[Role] = []
            if role_ids:
                roles = self.db.query(Role).filter(Role.id.in_(role_ids)).all()
            user.roles = roles

        self.db.commit()
        return user

    def toggle_user_status(self, user: User) -> User:
        user.is_active = not user.is_active
        self.db.commit()
        return user

    # ------------------------------------------------------------------ #
    # Roles and Permissions
    # ------------------------------------------------------------------ #
    def list_roles(self, system_first: bool = False) -> list[Role]:
        query = self.db.query(Role)
        if system_first:
            query = query.order_by(Role.is_system.desc(), Role.name)
        else:
            query = query.order_by(Role.name)
        return query.all()

    def get_role(self, role_id: str | int) -> Optional[Role]:
        return self.db.query(Role).filter(Role.id == role_id).first()

    def list_permissions(self) -> list[Permission]:
        return self.db.query(Permission).order_by(Permission.category, Permission.name).all()

    def list_permission_categories(self) -> list[PermissionCategory]:
        return self.db.query(PermissionCategory).order_by(
            PermissionCategory.display_order,
            PermissionCategory.name,
        ).all()

    def list_permissions_for_category(
        self,
        category: Optional[str],
    ) -> list[Permission]:
        query = self.db.query(Permission)
        if category:
            cat = self.db.query(PermissionCategory).filter(PermissionCategory.name == category).first()
            if cat:
                query = query.filter(Permission.category_id == cat.id)
        return query.order_by(Permission.category, Permission.name).all()

    def create_role(
        self,
        *,
        name: str,
        description: Optional[str],
        permission_ids: list[str],
    ) -> Optional[Role]:
        existing = self.db.query(Role).filter(Role.name == name).first()
        if existing:
            return None

        permissions: list[Permission] = []
        if permission_ids:
            permissions = self.db.query(Permission).filter(Permission.id.in_(permission_ids)).all()

        role = Role(
            name=name,
            description=description,
            is_system=False,
            permissions=permissions,
        )
        self.db.add(role)
        self.db.commit()
        return role

    def update_role(
        self,
        role: Role,
        *,
        name: str,
        description: Optional[str],
        permission_ids: list[str],
    ) -> Role:
        role.name = name
        role.description = description

        permissions: list[Permission] = []
        if permission_ids:
            permissions = self.db.query(Permission).filter(Permission.id.in_(permission_ids)).all()
        role.permissions = permissions

        self.db.commit()
        return role

    def delete_role(self, role: Role) -> None:
        self.db.delete(role)
        self.db.commit()

    # ------------------------------------------------------------------ #
    # Service Tokens
    # ------------------------------------------------------------------ #
    def list_tokens(self) -> list[ServiceToken]:
        return self.db.query(ServiceToken).order_by(ServiceToken.created_at.desc()).all()

    def create_token(
        self,
        *,
        name: str,
        scopes: list[str],
        expires_days: int,
        created_by_id: int,
    ) -> tuple[ServiceToken, str]:
        token_value = py_secrets.token_urlsafe(32)
        token_prefix = token_value[:8]

        token = ServiceToken(
            name=name,
            token_prefix=token_prefix,
            token_hash=token_value,
            scopes=scopes,
            expires_at=datetime.utcnow() + timedelta(days=expires_days),
            created_by_id=created_by_id,
        )
        self.db.add(token)
        self.db.commit()
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="admin.token.create",
            user_id=created_by_id,
            entity_type="service_token",
            entity_id=str(token.id),
            summary=f"Created service token '{name}'",
            metadata={"scopes": scopes, "expires_at": token.expires_at.isoformat()},
        )
        return token, token_value

    def revoke_token(self, token_id: str | int) -> Optional[ServiceToken]:
        token = self.db.query(ServiceToken).filter(ServiceToken.id == token_id).first()
        if not token:
            return None
        token_name = token.name
        self.db.delete(token)
        self.db.commit()
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="admin.token.revoke",
            entity_type="service_token",
            entity_id=str(token_id),
            summary=f"Revoked service token '{token_name}'",
        )
        return token

    # ------------------------------------------------------------------ #
    # Audit Log
    # ------------------------------------------------------------------ #
    def list_audit_log(
        self,
        *,
        q: Optional[str],
        group: Optional[str],
        action: Optional[str],
        page: int,
        per_page: int,
    ) -> tuple[list[SettingsAuditLog], int]:
        query = self.db.query(SettingsAuditLog)
        if q:
            query = query.filter(SettingsAuditLog.user_email.ilike(f"%{q}%"))
        if group:
            query = query.filter(SettingsAuditLog.group_name == group)
        if action:
            query = query.filter(SettingsAuditLog.action == action)

        total = query.count()
        entries = (
            query.order_by(SettingsAuditLog.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return entries, total

    # ------------------------------------------------------------------ #
    # Activity Log
    # ------------------------------------------------------------------ #
    def list_activity_log(
        self,
        *,
        q: Optional[str],
        action: Optional[str],
        entity_type: Optional[str],
        page: int,
        per_page: int,
    ) -> tuple[list[ActivityLog], int]:
        query = self.db.query(ActivityLog)
        if q:
            search_filter = or_(
                ActivityLog.user_email.ilike(f"%{q}%"),
                ActivityLog.summary.ilike(f"%{q}%"),
            )
            query = query.filter(search_filter)
        if action:
            query = query.filter(ActivityLog.action == action)
        if entity_type:
            query = query.filter(ActivityLog.entity_type == entity_type)

        total = query.count()
        entries = (
            query.order_by(ActivityLog.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return entries, total

    # ------------------------------------------------------------------ #
    # Webhooks
    # ------------------------------------------------------------------ #
    def list_webhooks(
        self,
        *,
        q: Optional[str],
        status: Optional[str],
        page: int,
        per_page: int,
    ) -> tuple[list[WebhookConfig], int]:
        query = self.db.query(WebhookConfig).filter(WebhookConfig.is_deleted == False)

        if q:
            search_filter = or_(
                WebhookConfig.name.ilike(f"%{q}%"),
                WebhookConfig.url.ilike(f"%{q}%"),
            )
            query = query.filter(search_filter)

        if status == "active":
            query = query.filter(WebhookConfig.is_active == True)
        elif status == "inactive":
            query = query.filter(WebhookConfig.is_active == False)

        total = query.count()
        webhooks = query.order_by(WebhookConfig.name).offset((page - 1) * per_page).limit(per_page).all()
        return webhooks, total

    def create_webhook(
        self,
        *,
        name: str,
        url: str,
        method: str,
        auth_type: str,
        auth_header: Optional[str],
        description: Optional[str],
        event_types: list[str],
        max_retries: int,
        created_by_id: int,
    ) -> tuple[WebhookConfig, str]:
        signing_secret = py_secrets.token_urlsafe(32)

        webhook = WebhookConfig(
            name=name,
            description=description,
            url=url,
            method=method,
            auth_type=auth_type,
            auth_header=auth_header,
            event_types=event_types,
            max_retries=max_retries,
            signing_secret=signing_secret,
            created_by_id=created_by_id,
        )
        self.db.add(webhook)
        self.db.commit()
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="admin.webhook.create",
            user_id=created_by_id,
            entity_type="webhook",
            entity_id=str(webhook.id),
            summary=f"Created webhook '{name}'",
            metadata={"url": url, "event_types": event_types},
        )
        return webhook, signing_secret

    def get_webhook(self, webhook_id: int) -> Optional[WebhookConfig]:
        return (
            self.db.query(WebhookConfig)
            .filter(
                WebhookConfig.id == webhook_id,
                WebhookConfig.is_deleted == False,
            )
            .first()
        )

    def list_webhook_deliveries(self, webhook_id: int, limit: int = 20) -> list[WebhookDelivery]:
        return (
            self.db.query(WebhookDelivery)
            .filter(WebhookDelivery.webhook_id == webhook_id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
            .all()
        )

    def update_webhook(
        self,
        webhook: WebhookConfig,
        *,
        name: str,
        url: str,
        method: str,
        auth_type: str,
        auth_header: Optional[str],
        description: Optional[str],
        event_types: list[str],
        max_retries: int,
        is_active: bool,
        updated_by_id: Optional[int] = None,
    ) -> WebhookConfig:
        webhook.name = name
        webhook.url = url
        webhook.method = method
        webhook.auth_type = auth_type
        webhook.auth_header = auth_header
        webhook.description = description
        webhook.event_types = event_types
        webhook.max_retries = max_retries
        webhook.is_active = is_active

        self.db.commit()
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="admin.webhook.update",
            user_id=updated_by_id,
            entity_type="webhook",
            entity_id=str(webhook.id),
            summary=f"Updated webhook '{webhook.name}'",
            metadata={"event_types": webhook.event_types, "is_active": webhook.is_active},
        )
        return webhook

    def toggle_webhook(self, webhook: WebhookConfig) -> WebhookConfig:
        webhook.is_active = not webhook.is_active
        self.db.commit()
        return webhook

    def delete_webhook(self, webhook: WebhookConfig, deleted_by_id: Optional[int] = None) -> None:
        webhook.is_deleted = True
        self.db.commit()
        activity_logger = ActivityLogger(self.db)
        activity_logger.log(
            action="admin.webhook.delete",
            user_id=deleted_by_id,
            entity_type="webhook",
            entity_id=str(webhook.id),
            summary=f"Deleted webhook '{webhook.name}'",
        )

    # ------------------------------------------------------------------ #
    # Groups
    # ------------------------------------------------------------------ #
    def list_groups(
        self,
        q: Optional[str],
        page: int,
        per_page: int,
    ) -> tuple[list[Group], int]:
        query = self.db.query(Group)
        if q:
            search_filter = or_(
                Group.name.ilike(f"%{q}%"),
                Group.description.ilike(f"%{q}%"),
            )
            query = query.filter(search_filter)

        total = query.count()
        groups = query.order_by(Group.name).offset((page - 1) * per_page).limit(per_page).all()
        return groups, total

    def get_group(self, group_id: int) -> Optional[Group]:
        return self.db.query(Group).filter(Group.id == group_id).first()

    def create_group(
        self,
        *,
        name: str,
        description: Optional[str],
        role_ids: list[str],
        created_by_id: int,
    ) -> Optional[Group]:
        existing = self.db.query(Group).filter(Group.name == name).first()
        if existing:
            return None

        group = Group(
            name=name,
            description=description,
            is_active=True,
            created_by_id=created_by_id,
        )
        self.db.add(group)
        self.db.flush()

        if role_ids:
            roles = self.db.query(Role).filter(Role.id.in_(role_ids)).all()
            for role in roles:
                group_role = GroupRole(
                    group_id=group.id,
                    role_id=role.id,
                    assigned_by_id=created_by_id,
                )
                self.db.add(group_role)

        self.db.commit()
        return group

    def update_group(
        self,
        group: Group,
        *,
        name: str,
        description: Optional[str],
        is_active: bool,
        role_ids: list[str],
        updated_by_id: int,
    ) -> Group:
        group.name = name
        group.description = description
        group.is_active = is_active

        self.db.query(GroupRole).filter(GroupRole.group_id == group.id).delete()

        if role_ids:
            roles = self.db.query(Role).filter(Role.id.in_(role_ids)).all()
            for role in roles:
                group_role = GroupRole(
                    group_id=group.id,
                    role_id=role.id,
                    assigned_by_id=updated_by_id,
                )
                self.db.add(group_role)

        self.db.commit()
        return group

    def list_available_group_users(self, group: Group, limit: int = 100) -> list[User]:
        member_ids = [m.user_id for m in group.members]
        query = self.db.query(User).filter(User.is_active == True)
        if member_ids:
            query = query.filter(~User.id.in_(member_ids))
        return query.order_by(User.email).limit(limit).all()

    def add_group_member(
        self,
        *,
        group_id: int,
        user_id: int,
        added_by_id: int,
    ) -> bool:
        existing = (
            self.db.query(GroupMember)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
            )
            .first()
        )

        if existing:
            return False

        member = GroupMember(
            group_id=group_id,
            user_id=user_id,
            added_by_id=added_by_id,
        )
        self.db.add(member)
        self.db.commit()
        return True

    def remove_group_member(
        self,
        *,
        group_id: int,
        user_id: int,
    ) -> bool:
        member = (
            self.db.query(GroupMember)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
            )
            .first()
        )
        if not member:
            return False
        self.db.delete(member)
        self.db.commit()
        return True

    def delete_group(self, group: Group) -> None:
        self.db.delete(group)
        self.db.commit()

    # ------------------------------------------------------------------ #
    # Sessions
    # ------------------------------------------------------------------ #
    def list_active_sessions(
        self,
        q: Optional[str],
        page: int,
        per_page: int,
    ) -> tuple[list[UserSession], int]:
        now = utc_now()

        query = self.db.query(UserSession).filter(
            and_(
                UserSession.is_active == True,
                UserSession.expires_at > now,
                UserSession.revoked_at.is_(None),
            )
        )

        if q:
            query = query.join(User).filter(User.email.ilike(f"%{q}%"))

        total = query.count()
        sessions = (
            query.order_by(UserSession.last_activity_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return sessions, total

    def revoke_session(
        self,
        *,
        session_id: str,
        revoked_by_id: Optional[int],
        reason: Optional[str],
    ) -> bool:
        session_service = SessionService(self.db)
        success = session_service.revoke_session(
            session_id=session_id,
            revoked_by_id=revoked_by_id,
            reason=reason,
        )
        if success:
            self.db.commit()
        return success

    def revoke_all_sessions(
        self,
        *,
        user_id: int,
        revoked_by_id: Optional[int],
        reason: Optional[str],
    ) -> int:
        session_service = SessionService(self.db)
        count = session_service.revoke_all_sessions(
            user_id=user_id,
            revoked_by_id=revoked_by_id,
            reason=reason,
        )
        if count:
            self.db.commit()
        return count

    # ------------------------------------------------------------------ #
    # User Permissions
    # ------------------------------------------------------------------ #
    def list_user_permissions(self, user_id: int) -> list[UserPermission]:
        return self.db.query(UserPermission).filter(UserPermission.user_id == user_id).all()

    def add_user_permission(
        self,
        *,
        user_id: int,
        permission_id: int,
        grant_type: str,
        reason: Optional[str],
        created_by_id: int,
    ) -> bool:
        existing = (
            self.db.query(UserPermission)
            .filter(
                UserPermission.user_id == user_id,
                UserPermission.permission_id == permission_id,
            )
            .first()
        )

        if existing:
            existing.grant_type = grant_type
            existing.reason = reason
            self.db.commit()
            return False

        perm = UserPermission(
            user_id=user_id,
            permission_id=permission_id,
            grant_type=grant_type,
            reason=reason,
            created_by_id=created_by_id,
        )
        self.db.add(perm)
        self.db.commit()
        return True

    def remove_user_permission(
        self,
        *,
        user_id: int,
        permission_id: int,
    ) -> bool:
        perm = (
            self.db.query(UserPermission)
            .filter(
                UserPermission.user_id == user_id,
                UserPermission.permission_id == permission_id,
            )
            .first()
        )
        if not perm:
            return False
        self.db.delete(perm)
        self.db.commit()
        return True
