from datetime import datetime
import structlog

from app.models.pop import Pop

logger = structlog.get_logger()


async def sync_locations(sync_client, client, full_sync: bool):
    """Sync POPs/locations from Splynx."""
    sync_client.start_sync("locations", "full" if full_sync else "incremental")

    try:
        locations = await sync_client._fetch_paginated(client, "/admin/administration/locations")

        for loc_data in locations:
            splynx_id = loc_data.get("id")
            existing = sync_client.db.query(Pop).filter(Pop.splynx_id == splynx_id).first()

            name = loc_data.get("name", "Unknown")

            if existing:
                existing.name = name
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                pop = Pop(
                    splynx_id=splynx_id,
                    name=name,
                )
                sync_client.db.add(pop)
                sync_client.increment_created()

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info("splynx_locations_synced", count=len(locations))

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
