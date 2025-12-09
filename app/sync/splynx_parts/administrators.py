from datetime import datetime
import structlog

from app.models.administrator import Administrator

logger = structlog.get_logger()


async def sync_administrators(sync_client, client, full_sync: bool):
    """Sync administrators from Splynx."""
    sync_client.start_sync("administrators", "full" if full_sync else "incremental")
    batch_size = 100

    try:
        admins = await sync_client._fetch_paginated(
            client, "/admin/administration/administrators"
        )
        logger.info("splynx_administrators_fetched", count=len(admins))

        for i, admin_data in enumerate(admins, 1):
            splynx_id = admin_data.get("id")
            existing = sync_client.db.query(Administrator).filter(
                Administrator.splynx_id == splynx_id
            ).first()

            # Parse last activity datetime
            last_activity = None
            if admin_data.get("last_dt"):
                try:
                    last_activity = datetime.strptime(admin_data["last_dt"], "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass

            if existing:
                existing.login = admin_data.get("login")
                existing.name = admin_data.get("name")
                existing.email = admin_data.get("email")
                existing.phone = admin_data.get("phone")
                existing.role_name = admin_data.get("role_name")
                existing.router_access = admin_data.get("router_access")
                existing.partner_id = admin_data.get("partner_id")
                existing.last_ip = admin_data.get("last_ip")
                existing.last_activity = last_activity
                existing.calendar_color = admin_data.get("calendar_color")
                existing.send_from_my_name = admin_data.get("send_from_my_name")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                admin = Administrator(
                    splynx_id=splynx_id,
                    login=admin_data.get("login"),
                    name=admin_data.get("name"),
                    email=admin_data.get("email"),
                    phone=admin_data.get("phone"),
                    role_name=admin_data.get("role_name"),
                    router_access=admin_data.get("router_access"),
                    partner_id=admin_data.get("partner_id"),
                    last_ip=admin_data.get("last_ip"),
                    last_activity=last_activity,
                    calendar_color=admin_data.get("calendar_color"),
                    send_from_my_name=admin_data.get("send_from_my_name"),
                )
                sync_client.db.add(admin)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("administrators_batch_committed", processed=i, total=len(admins))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_administrators_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
