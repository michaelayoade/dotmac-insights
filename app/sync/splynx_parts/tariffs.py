from datetime import datetime
import json
import structlog

from app.models.tariff import Tariff, TariffType

logger = structlog.get_logger()


async def sync_tariffs(sync_client, client, full_sync: bool):
    """Sync all tariff types from Splynx (internet, recurring, one-time)."""
    sync_client.start_sync("tariffs", "full" if full_sync else "incremental")

    try:
        total_created = 0
        total_updated = 0

        # Sync Internet Tariffs
        internet_tariffs = await sync_client._fetch_paginated(client, "/admin/tariffs/internet")
        logger.info("splynx_internet_tariffs_fetched", count=len(internet_tariffs))

        for tariff_data in internet_tariffs:
            created, updated = _upsert_tariff(sync_client, tariff_data, TariffType.INTERNET)
            total_created += created
            total_updated += updated

        # Sync Recurring Tariffs
        recurring_tariffs = await sync_client._fetch_paginated(client, "/admin/tariffs/recurring")
        logger.info("splynx_recurring_tariffs_fetched", count=len(recurring_tariffs))

        for tariff_data in recurring_tariffs:
            created, updated = _upsert_tariff(sync_client, tariff_data, TariffType.RECURRING)
            total_created += created
            total_updated += updated

        # Sync One-Time Tariffs
        onetime_tariffs = await sync_client._fetch_paginated(client, "/admin/tariffs/one-time")
        logger.info("splynx_onetime_tariffs_fetched", count=len(onetime_tariffs))

        for tariff_data in onetime_tariffs:
            created, updated = _upsert_tariff(sync_client, tariff_data, TariffType.ONE_TIME)
            total_created += created
            total_updated += updated

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_tariffs_synced",
            created=total_created,
            updated=total_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise


def _upsert_tariff(sync_client, tariff_data: dict, tariff_type: TariffType) -> tuple:
    """Insert or update a single tariff. Returns (created, updated) counts."""
    splynx_id = tariff_data.get("id")
    existing = sync_client.db.query(Tariff).filter(
        Tariff.splynx_id == splynx_id,
        Tariff.tariff_type == tariff_type,
    ).first()

    price = float(tariff_data.get("price", 0) or 0)
    vat_percent = float(tariff_data.get("vat_percent", 0) or 0)
    with_vat = tariff_data.get("with_vat") == "1"

    # Speed fields (only for internet tariffs)
    speed_download = tariff_data.get("speed_download")
    speed_upload = tariff_data.get("speed_upload")

    # Billing types as JSON string
    billing_types = tariff_data.get("billing_types")
    billing_types_str = json.dumps(billing_types) if billing_types else None

    # Availability flags
    available_for_services = tariff_data.get("available_for_services") == "1"
    show_on_portal = tariff_data.get("show_on_customer_portal") == "1"
    enabled = tariff_data.get("enabled", "1") == "1"
    deleted = tariff_data.get("deleted", "0") == "1"

    if existing:
        existing.title = tariff_data.get("title", "")
        existing.service_name = tariff_data.get("service_name")
        existing.price = price
        existing.vat_percent = vat_percent
        existing.with_vat = with_vat
        existing.speed_download = speed_download
        existing.speed_upload = speed_upload
        existing.billing_types = billing_types_str
        existing.available_for_services = available_for_services
        existing.show_on_customer_portal = show_on_portal
        existing.enabled = enabled and not deleted
        existing.last_synced_at = datetime.utcnow()
        sync_client.increment_updated()
        return (0, 1)
    else:
        tariff = Tariff(
            splynx_id=splynx_id,
            tariff_type=tariff_type,
            title=tariff_data.get("title", ""),
            service_name=tariff_data.get("service_name"),
            price=price,
            vat_percent=vat_percent,
            with_vat=with_vat,
            speed_download=speed_download,
            speed_upload=speed_upload,
            billing_types=billing_types_str,
            available_for_services=available_for_services,
            show_on_customer_portal=show_on_portal,
            enabled=enabled and not deleted,
        )
        sync_client.db.add(tariff)
        sync_client.increment_created()
        return (1, 0)
