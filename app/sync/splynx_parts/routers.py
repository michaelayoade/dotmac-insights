from datetime import datetime
import json
import structlog

from app.models.router import Router
from app.models.pop import Pop

logger = structlog.get_logger()


def serialize_json_field(value):
    """Serialize a value to JSON string if it's a list or dict."""
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return str(value)


async def sync_routers(sync_client, client, full_sync: bool):
    """Sync network routers/NAS from Splynx."""
    sync_client.start_sync("routers", "full" if full_sync else "incremental")

    try:
        routers = await sync_client._fetch_paginated(client, "/admin/networking/routers")
        logger.info("splynx_routers_fetched", count=len(routers))

        # Pre-fetch POPs for FK lookup
        pops_by_splynx_id = {
            pop.splynx_id: pop.id
            for pop in sync_client.db.query(Pop).filter(Pop.splynx_id.isnot(None)).all()
        }

        for router_data in routers:
            splynx_id = router_data.get("id")
            existing = sync_client.db.query(Router).filter(Router.splynx_id == splynx_id).first()

            # Find POP by location_id
            location_id = router_data.get("location_id")
            pop_id = pops_by_splynx_id.get(location_id) if location_id else None

            # Serialize JSON fields
            pool_ids = serialize_json_field(router_data.get("pool_ids"))
            partners_ids = serialize_json_field(router_data.get("partners_ids"))
            additional_attributes = serialize_json_field(router_data.get("additional_attributes"))

            if existing:
                existing.title = router_data.get("title", "")
                existing.model = router_data.get("model")
                existing.location_id = location_id
                existing.pop_id = pop_id
                existing.address = router_data.get("address")
                existing.gps = router_data.get("gps")
                existing.ip = router_data.get("ip")
                existing.nas_ip = router_data.get("nas_ip")
                existing.nas_type = router_data.get("nas_type")
                # RADIUS/NAS config
                existing.radius_secret = router_data.get("radius_secret")
                existing.radius_coa_port = router_data.get("coa_port")
                existing.radius_accounting_interval = router_data.get("accounting_interval")
                # Auth methods
                existing.authorization_method = router_data.get("authorization_method")
                existing.accounting_method = router_data.get("accounting_method")
                # API access
                existing.api_login = router_data.get("api_login")
                existing.api_password = router_data.get("api_password")
                existing.api_port = router_data.get("api_port")
                existing.ssh_port = router_data.get("ssh_port")
                # JSON fields
                existing.pool_ids = pool_ids
                existing.partners_ids = partners_ids
                existing.additional_attributes = additional_attributes
                existing.status = router_data.get("status")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                router = Router(
                    splynx_id=splynx_id,
                    title=router_data.get("title", ""),
                    model=router_data.get("model"),
                    location_id=location_id,
                    pop_id=pop_id,
                    address=router_data.get("address"),
                    gps=router_data.get("gps"),
                    ip=router_data.get("ip"),
                    nas_ip=router_data.get("nas_ip"),
                    nas_type=router_data.get("nas_type"),
                    # RADIUS/NAS config
                    radius_secret=router_data.get("radius_secret"),
                    radius_coa_port=router_data.get("coa_port"),
                    radius_accounting_interval=router_data.get("accounting_interval"),
                    # Auth methods
                    authorization_method=router_data.get("authorization_method"),
                    accounting_method=router_data.get("accounting_method"),
                    # API access
                    api_login=router_data.get("api_login"),
                    api_password=router_data.get("api_password"),
                    api_port=router_data.get("api_port"),
                    ssh_port=router_data.get("ssh_port"),
                    # JSON fields
                    pool_ids=pool_ids,
                    partners_ids=partners_ids,
                    additional_attributes=additional_attributes,
                    status=router_data.get("status"),
                )
                sync_client.db.add(router)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_routers_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
