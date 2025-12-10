from datetime import datetime
import structlog

from app.models.lead import Lead
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


async def sync_leads(sync_client, client, full_sync: bool):
    """Sync CRM leads from Splynx."""
    sync_client.start_sync("leads", "full" if full_sync else "incremental")
    batch_size = settings.sync_batch_size

    try:
        leads = await sync_client._fetch_paginated(
            client, "/admin/crm/leads"
        )
        logger.info("splynx_leads_fetched", count=len(leads))

        # Pre-fetch customer lookup by splynx_id for conversion linking
        customer_map = {}
        customers = sync_client.db.query(Customer.id, Customer.splynx_id).all()
        for cust in customers:
            if cust.splynx_id:
                customer_map[cust.splynx_id] = cust.id

        for i, lead_data in enumerate(leads, 1):
            splynx_id = lead_data.get("id")
            existing = sync_client.db.query(Lead).filter(
                Lead.splynx_id == splynx_id
            ).first()

            # Try to link to converted customer if status is active
            # TODO: Will be linked via separate logic if needed
            # if lead_data.get("condition") == "active":
            #     customer_id = find_matching_customer()

            if existing:
                existing.name = lead_data.get("name")
                existing.email = lead_data.get("email")
                existing.billing_email = lead_data.get("billing_email")
                existing.phone = lead_data.get("phone")
                existing.login = lead_data.get("login")
                existing.category = lead_data.get("category")
                existing.street_1 = lead_data.get("street_1")
                existing.street_2 = lead_data.get("street_2")
                existing.city = lead_data.get("city")
                existing.zip_code = lead_data.get("zip_code")
                existing.gps = lead_data.get("gps")
                existing.location_id = lead_data.get("location_id")
                existing.partner_id = lead_data.get("partner_id")
                existing.added_by = lead_data.get("added_by")
                existing.added_by_id = lead_data.get("added_by_id")
                existing.status = lead_data.get("status")
                existing.condition = lead_data.get("condition")
                existing.billing_type = lead_data.get("billing_type")
                existing.date_add = parse_datetime(lead_data.get("date_add"))
                existing.last_online = parse_datetime(lead_data.get("last_online"))
                existing.last_update = parse_datetime(lead_data.get("last_update"))
                existing.conversion_date = parse_datetime(lead_data.get("conversion_date"))
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                lead = Lead(
                    splynx_id=splynx_id,
                    name=lead_data.get("name"),
                    email=lead_data.get("email"),
                    billing_email=lead_data.get("billing_email"),
                    phone=lead_data.get("phone"),
                    login=lead_data.get("login"),
                    category=lead_data.get("category"),
                    street_1=lead_data.get("street_1"),
                    street_2=lead_data.get("street_2"),
                    city=lead_data.get("city"),
                    zip_code=lead_data.get("zip_code"),
                    gps=lead_data.get("gps"),
                    location_id=lead_data.get("location_id"),
                    partner_id=lead_data.get("partner_id"),
                    added_by=lead_data.get("added_by"),
                    added_by_id=lead_data.get("added_by_id"),
                    status=lead_data.get("status"),
                    condition=lead_data.get("condition"),
                    billing_type=lead_data.get("billing_type"),
                    date_add=parse_datetime(lead_data.get("date_add")),
                    last_online=parse_datetime(lead_data.get("last_online")),
                    last_update=parse_datetime(lead_data.get("last_update")),
                    conversion_date=parse_datetime(lead_data.get("conversion_date")),
                    last_synced_at=datetime.utcnow(),
                )
                sync_client.db.add(lead)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("leads_batch_committed", processed=i, total=len(leads))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_leads_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
