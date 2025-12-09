from datetime import datetime
import structlog
import httpx

from app.models.ipv4_network import IPv4Network

logger = structlog.get_logger()


async def sync_ipv4_networks(sync_client, client: httpx.AsyncClient, full_sync: bool):
    """Sync IPv4 networks/subnets from Splynx.

    Syncs network definitions including:
    - Network address and mask
    - Network type (rootnet/endnet)
    - Type of usage (pool/static/management)
    - Location and hierarchy
    """
    sync_client.start_sync("ipv4_networks", "full" if full_sync else "incremental")

    try:
        # Fetch all IPv4 networks
        networks = await sync_client._fetch_paginated(
            client, "/admin/networking/ipv4"
        )
        logger.info("splynx_ipv4_networks_fetched", count=len(networks))

        for net_data in networks:
            try:
                splynx_id = net_data.get("id")
                if not splynx_id:
                    continue

                existing = sync_client.db.query(IPv4Network).filter(
                    IPv4Network.splynx_id == splynx_id
                ).first()

                network_addr = net_data.get("network", "")
                mask = int(net_data.get("mask", 0) or 0)

                if existing:
                    existing.network = network_addr
                    existing.mask = mask
                    existing.title = net_data.get("title")
                    existing.comment = net_data.get("comment")
                    existing.network_type = net_data.get("network_type")
                    existing.type_of_usage = net_data.get("type_of_usage")
                    existing.network_category = net_data.get("network_category")
                    existing.parent_id = net_data.get("parent")
                    existing.rootnet = net_data.get("rootnet")
                    existing.location_id = net_data.get("location_id")
                    existing.used = net_data.get("used")
                    existing.allow_use_network_and_broadcast = bool(
                        net_data.get("allow_use_network_and_broadcast")
                    )
                    existing.last_synced_at = datetime.utcnow()
                    sync_client.increment_updated()
                else:
                    network = IPv4Network(
                        splynx_id=splynx_id,
                        network=network_addr,
                        mask=mask,
                        title=net_data.get("title"),
                        comment=net_data.get("comment"),
                        network_type=net_data.get("network_type"),
                        type_of_usage=net_data.get("type_of_usage"),
                        network_category=net_data.get("network_category"),
                        parent_id=net_data.get("parent"),
                        rootnet=net_data.get("rootnet"),
                        location_id=net_data.get("location_id"),
                        used=net_data.get("used"),
                        allow_use_network_and_broadcast=bool(
                            net_data.get("allow_use_network_and_broadcast")
                        ),
                        last_synced_at=datetime.utcnow(),
                    )
                    sync_client.db.add(network)
                    sync_client.increment_created()

            except Exception as e:
                logger.warning(
                    "splynx_ipv4_network_sync_error",
                    network_id=net_data.get("id"),
                    error=str(e)
                )
                continue

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_ipv4_networks_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
