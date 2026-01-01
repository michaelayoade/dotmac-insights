from __future__ import annotations

import structlog

from app.database import SessionLocal
from app.models.auth import Role, Permission, RolePermission

logger = structlog.get_logger()


def ensure_admin_has_all_permissions() -> None:
    """Ensure the admin role has every permission in the system."""
    session = SessionLocal()
    try:
        wildcard = session.query(Permission).filter(Permission.scope == "*").first()
        if not wildcard:
            wildcard = Permission(scope="*", description="Full access", category="admin")
            session.add(wildcard)
            session.flush()

        admin_role = session.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(
                name="admin",
                description="Full system access",
                is_system=True,
            )
            session.add(admin_role)
            session.flush()
            logger.info("admin_role_created", role_id=admin_role.id)

        permission_ids = [row[0] for row in session.query(Permission.id).all()]
        if not permission_ids:
            logger.warning("permissions_missing")
            return

        existing = {
            row[0]
            for row in session.query(RolePermission.permission_id)
            .filter(RolePermission.role_id == admin_role.id)
            .all()
        }
        missing = [perm_id for perm_id in permission_ids if perm_id not in existing]

        if not missing:
            return

        session.bulk_save_objects(
            [RolePermission(role_id=admin_role.id, permission_id=perm_id) for perm_id in missing]
        )
        session.commit()
        logger.info("admin_permissions_synced", added=len(missing))
    except Exception as exc:
        session.rollback()
        logger.error("admin_permissions_sync_failed", error=str(exc))
    finally:
        session.close()
