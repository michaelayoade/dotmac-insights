from datetime import datetime
import structlog

from app.models.network_monitor import NetworkMonitor, MonitorState

logger = structlog.get_logger()


async def sync_network_monitors(sync_client, client, full_sync: bool):
    """Sync network monitoring devices from Splynx."""
    sync_client.start_sync("network_monitors", "full" if full_sync else "incremental")
    batch_size = 100

    try:
        monitors = await sync_client._fetch_paginated(
            client, "/admin/networking/monitoring"
        )
        logger.info("splynx_network_monitors_fetched", count=len(monitors))

        for i, monitor_data in enumerate(monitors, 1):
            splynx_id = monitor_data.get("id")
            existing = sync_client.db.query(NetworkMonitor).filter(
                NetworkMonitor.splynx_id == splynx_id
            ).first()

            # Map ping state
            ping_state_str = (monitor_data.get("ping_state") or "").lower()
            ping_state_map = {
                "up": MonitorState.UP,
                "down": MonitorState.DOWN,
            }
            ping_state = ping_state_map.get(ping_state_str, MonitorState.UNKNOWN)

            # Map SNMP state
            snmp_state_str = (monitor_data.get("snmp_state") or "").lower()
            snmp_state_map = {
                "up": MonitorState.UP,
                "down": MonitorState.DOWN,
            }
            snmp_state = snmp_state_map.get(snmp_state_str, MonitorState.UNKNOWN)

            if existing:
                existing.title = monitor_data.get("title")
                existing.producer = str(monitor_data.get("producer")) if monitor_data.get("producer") else None
                existing.model = monitor_data.get("model")
                existing.ip_address = monitor_data.get("ip")
                existing.snmp_port = monitor_data.get("snmp_port")
                existing.snmp_community = monitor_data.get("snmp_community")
                existing.snmp_version = monitor_data.get("snmp_version")
                existing.device_type = monitor_data.get("type")
                existing.monitoring_group = monitor_data.get("monitoring_group")
                existing.location_id = monitor_data.get("location_id")
                existing.network_site_id = monitor_data.get("network_site_id")
                existing.parent_id = monitor_data.get("parent_id")
                existing.address = monitor_data.get("address")
                existing.gps = monitor_data.get("gps")
                existing.active = monitor_data.get("active") == "1"
                existing.send_notifications = monitor_data.get("send_notifications") == "1"
                existing.access_device = monitor_data.get("access_device") == "1"
                existing.is_ping = monitor_data.get("is_ping") == "1"
                existing.ping_state = ping_state
                existing.ping_time = monitor_data.get("ping_time")
                existing.snmp_state = snmp_state
                existing.snmp_time = monitor_data.get("snmp_time")
                existing.snmp_uptime = monitor_data.get("snmp_uptime")
                existing.snmp_status = monitor_data.get("snmp_status")
                existing.delay_timer = monitor_data.get("delay_timer")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                monitor = NetworkMonitor(
                    splynx_id=splynx_id,
                    title=monitor_data.get("title"),
                    producer=str(monitor_data.get("producer")) if monitor_data.get("producer") else None,
                    model=monitor_data.get("model"),
                    ip_address=monitor_data.get("ip"),
                    snmp_port=monitor_data.get("snmp_port"),
                    snmp_community=monitor_data.get("snmp_community"),
                    snmp_version=monitor_data.get("snmp_version"),
                    device_type=monitor_data.get("type"),
                    monitoring_group=monitor_data.get("monitoring_group"),
                    location_id=monitor_data.get("location_id"),
                    network_site_id=monitor_data.get("network_site_id"),
                    parent_id=monitor_data.get("parent_id"),
                    address=monitor_data.get("address"),
                    gps=monitor_data.get("gps"),
                    active=monitor_data.get("active") == "1",
                    send_notifications=monitor_data.get("send_notifications") == "1",
                    access_device=monitor_data.get("access_device") == "1",
                    is_ping=monitor_data.get("is_ping") == "1",
                    ping_state=ping_state,
                    ping_time=monitor_data.get("ping_time"),
                    snmp_state=snmp_state,
                    snmp_time=monitor_data.get("snmp_time"),
                    snmp_uptime=monitor_data.get("snmp_uptime"),
                    snmp_status=monitor_data.get("snmp_status"),
                    delay_timer=monitor_data.get("delay_timer"),
                )
                sync_client.db.add(monitor)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("network_monitors_batch_committed", processed=i, total=len(monitors))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_network_monitors_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
