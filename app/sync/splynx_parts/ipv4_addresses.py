from datetime import datetime
import structlog

from app.models.ipv4_address import IPv4Address
from app.models.customer import Customer
from app.config import settings

logger = structlog.get_logger()


def parse_datetime(value):
    """Parse datetime from various Splynx formats."""
    if not value or value == "0000-00-00 00:00:00":
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None


async def sync_ipv4_addresses(sync_client, client, full_sync: bool):
    """Sync IPv4 addresses from Splynx."""
    sync_client.start_sync("ipv4_addresses", "full" if full_sync else "incremental")
    batch_size = settings.sync_batch_size

    try:
        ips = await sync_client._fetch_paginated(
            client, "/admin/networking/ipv4-ip"
        )
        logger.info("splynx_ipv4_addresses_fetched", count=len(ips))

        # Pre-fetch customer lookup by splynx_id
        customer_map = {}
        customers = sync_client.db.query(Customer.id, Customer.splynx_id).all()
        for cust in customers:
            if cust.splynx_id:
                customer_map[cust.splynx_id] = cust.id

        for i, ip_data in enumerate(ips, 1):
            splynx_id = ip_data.get("id")
            existing = sync_client.db.query(IPv4Address).filter(
                IPv4Address.splynx_id == splynx_id
            ).first()

            # Map customer
            splynx_customer_id = ip_data.get("customer_id")
            customer_id = customer_map.get(splynx_customer_id) if splynx_customer_id else None

            # Parse is_used
            is_used = ip_data.get("is_used")
            if isinstance(is_used, str):
                is_used = is_used.lower() in ("1", "true", "yes")
            elif isinstance(is_used, int):
                is_used = bool(is_used)
            else:
                is_used = False

            if existing:
                existing.ip = ip_data.get("ip")
                existing.hostname = ip_data.get("hostname")
                existing.title = ip_data.get("title")
                existing.comment = ip_data.get("comment")
                existing.ipv4_network_id = ip_data.get("ipv4_networks_id")
                existing.host_category = ip_data.get("host_category")
                existing.module = ip_data.get("module")
                existing.module_item_id = ip_data.get("module_item_id")
                existing.customer_id = customer_id
                existing.card_id = ip_data.get("card_id")
                existing.location_id = ip_data.get("location_id")
                existing.is_used = is_used
                existing.status = ip_data.get("status")
                existing.last_check = parse_datetime(ip_data.get("last_check"))
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                ip_addr = IPv4Address(
                    splynx_id=splynx_id,
                    ip=ip_data.get("ip"),
                    hostname=ip_data.get("hostname"),
                    title=ip_data.get("title"),
                    comment=ip_data.get("comment"),
                    ipv4_network_id=ip_data.get("ipv4_networks_id"),
                    host_category=ip_data.get("host_category"),
                    module=ip_data.get("module"),
                    module_item_id=ip_data.get("module_item_id"),
                    customer_id=customer_id,
                    card_id=ip_data.get("card_id"),
                    location_id=ip_data.get("location_id"),
                    is_used=is_used,
                    status=ip_data.get("status"),
                    last_check=parse_datetime(ip_data.get("last_check")),
                    last_synced_at=datetime.utcnow(),
                )
                sync_client.db.add(ip_addr)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("ipv4_addresses_batch_committed", processed=i, total=len(ips))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_ipv4_addresses_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
