from datetime import datetime
from typing import Any, Optional
import structlog
import httpx

from app.models.ipv6_network import IPv6Network

logger = structlog.get_logger()


def _safe_int(val: Any) -> Optional[int]:
    """Convert a value to int, returning None if not possible."""
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


async def sync_ipv6_networks(sync_client, client: httpx.AsyncClient, full_sync: bool):
    """Sync IPv6 networks/subnets from Splynx.

    Syncs network definitions including:
    - Network address and prefix
    - Network type (rootnet/endnet)
    - Type of usage (pool/static/management)
    - Location and hierarchy
    """
    sync_client.start_sync("ipv6_networks", "full" if full_sync else "incremental")

    try:
        # Fetch all IPv6 networks
        networks = await sync_client._fetch_paginated(
            client, "/admin/networking/ipv6"
        )
        logger.info("splynx_ipv6_networks_fetched", count=len(networks))

        for net_data in networks:
            try:
                raw_id = net_data.get("id")
                if not raw_id:
                    continue
                splynx_id = int(raw_id)

                existing = sync_client.db.query(IPv6Network).filter(
                    IPv6Network.splynx_id == splynx_id
                ).first()

                network_addr = net_data.get("network", "")
                prefix = int(net_data.get("prefix", 0) or 0)

                # Parse integer fields safely
                network_category = _safe_int(net_data.get("network_category"))
                parent_id = _safe_int(net_data.get("parent"))
                rootnet = _safe_int(net_data.get("rootnet"))
                location_id = _safe_int(net_data.get("location_id"))
                used = _safe_int(net_data.get("used"))

                if existing:
                    existing.network = network_addr
                    existing.prefix = prefix
                    existing.title = net_data.get("title")
                    existing.comment = net_data.get("comment")
                    existing.network_type = net_data.get("network_type")
                    existing.type_of_usage = net_data.get("type_of_usage")
                    existing.network_category = network_category
                    existing.parent_id = parent_id
                    existing.rootnet = rootnet
                    existing.location_id = location_id
                    existing.used = used
                    existing.last_synced_at = datetime.utcnow()
                    sync_client.increment_updated()
                else:
                    network = IPv6Network(
                        splynx_id=splynx_id,
                        network=network_addr,
                        prefix=prefix,
                        title=net_data.get("title"),
                        comment=net_data.get("comment"),
                        network_type=net_data.get("network_type"),
                        type_of_usage=net_data.get("type_of_usage"),
                        network_category=network_category,
                        parent_id=parent_id,
                        rootnet=rootnet,
                        location_id=location_id,
                        used=used,
                        last_synced_at=datetime.utcnow(),
                    )
                    sync_client.db.add(network)
                    sync_client.increment_created()

            except Exception as e:
                logger.warning(
                    "splynx_ipv6_network_sync_error",
                    network_id=net_data.get("id"),
                    error=str(e)
                )
                continue

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_ipv6_networks_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
