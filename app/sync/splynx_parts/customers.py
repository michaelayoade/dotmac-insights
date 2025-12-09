from datetime import datetime
import structlog

from app.models.customer import Customer, CustomerStatus, CustomerType, BillingType
from app.models.pop import Pop

logger = structlog.get_logger()


def _parse_date(date_str: str, fmt: str = "%Y-%m-%d") -> datetime | None:
    """Parse date string to datetime, return None if invalid."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, fmt)
    except (ValueError, TypeError):
        return None


def _parse_datetime(dt_str: str) -> datetime | None:
    """Parse datetime string (YYYY-MM-DD HH:MM:SS) to datetime."""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


async def sync_customers(sync_client, client, full_sync: bool):
    """Sync customers from Splynx."""
    sync_client.start_sync("customers", "full" if full_sync else "incremental")
    batch_size = 500  # Commit every 500 records

    try:
        customers = await sync_client._fetch_paginated(client, "/admin/customers/customer")
        logger.info("splynx_customers_fetched", count=len(customers))

        # Pre-fetch all POPs for faster lookup
        pops_by_splynx_id = {
            pop.splynx_id: pop.id
            for pop in sync_client.db.query(Pop).all()
        }

        for i, cust_data in enumerate(customers, 1):
            splynx_id = cust_data.get("id")
            existing = sync_client.db.query(Customer).filter(Customer.splynx_id == splynx_id).first()

            # Map Splynx status to our status
            splynx_status = str(cust_data.get("status", "active")).lower()
            status_map = {
                "active": CustomerStatus.ACTIVE,
                "inactive": CustomerStatus.INACTIVE,
                "blocked": CustomerStatus.SUSPENDED,
                "disabled": CustomerStatus.CANCELLED,
                "new": CustomerStatus.ACTIVE,
            }
            status = status_map.get(splynx_status, CustomerStatus.ACTIVE)

            # Find POP if location_id exists (using pre-fetched map)
            pop_id = None
            location_id = cust_data.get("location_id")
            if location_id:
                pop_id = pops_by_splynx_id.get(int(location_id))

            # Map category to customer type
            category = str(cust_data.get("category", "")).lower()
            customer_type = CustomerType.RESIDENTIAL
            if category in ["company", "business", "corporate", "enterprise"]:
                customer_type = CustomerType.BUSINESS

            # Map billing type
            billing_type_str = str(cust_data.get("billing_type", "")).lower()
            billing_type_map = {
                "prepaid": BillingType.PREPAID,
                "prepaid_monthly": BillingType.PREPAID_MONTHLY,
                "recurring": BillingType.RECURRING,
            }
            billing_type = billing_type_map.get(billing_type_str)

            # Extract additional_attributes (custom fields)
            attrs = cust_data.get("additional_attributes", {}) or {}
            base_station = attrs.get("base_station") or None
            building_type = attrs.get("building_type") or None
            referrer = attrs.get("referrer") or None
            zoho_id = attrs.get("zoho_id") or None
            vat_id = attrs.get("vat_id") or None

            # Extract labels
            labels_list = cust_data.get("customer_labels", [])
            labels = ",".join(labels_list) if labels_list else None

            # Parse MRR
            mrr = None
            mrr_str = cust_data.get("mrr_total")
            if mrr_str:
                try:
                    mrr = float(mrr_str)
                except (ValueError, TypeError):
                    pass

            # Parse daily prepaid cost
            daily_cost = None
            daily_cost_str = cust_data.get("daily_prepaid_cost")
            if daily_cost_str:
                try:
                    daily_cost = float(daily_cost_str)
                except (ValueError, TypeError):
                    pass

            if existing:
                # Basic info
                existing.name = cust_data.get("name", "")
                existing.email = cust_data.get("email") or None
                existing.billing_email = cust_data.get("billing_email") or None
                existing.phone = cust_data.get("phone") or None

                # Address
                existing.address = cust_data.get("street_1") or None
                existing.address_2 = cust_data.get("street_2") or None
                existing.city = cust_data.get("city") or None
                existing.zip_code = cust_data.get("zip_code") or None
                existing.gps = cust_data.get("gps") or None

                # Classification
                existing.status = status
                existing.customer_type = customer_type
                existing.billing_type = billing_type
                existing.pop_id = pop_id

                # Network/Infrastructure
                existing.base_station = base_station
                existing.building_type = building_type

                # Account info
                existing.account_number = cust_data.get("login")
                existing.vat_id = vat_id
                existing.zoho_id = zoho_id

                # Financial
                existing.mrr = mrr
                existing.daily_prepaid_cost = daily_cost

                # Partner
                existing.partner_id = cust_data.get("partner_id")

                # Dates
                existing.signup_date = _parse_date(cust_data.get("date_add"))
                existing.conversion_date = _parse_date(cust_data.get("conversion_date"))
                existing.last_online = _parse_datetime(cust_data.get("last_online"))

                # Attribution
                existing.added_by = cust_data.get("added_by")
                existing.added_by_id = cust_data.get("added_by_id")
                existing.referrer = referrer

                # Labels
                existing.labels = labels

                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                customer = Customer(
                    splynx_id=splynx_id,
                    # Basic info
                    name=cust_data.get("name", ""),
                    email=cust_data.get("email") or None,
                    billing_email=cust_data.get("billing_email") or None,
                    phone=cust_data.get("phone") or None,
                    # Address
                    address=cust_data.get("street_1") or None,
                    address_2=cust_data.get("street_2") or None,
                    city=cust_data.get("city") or None,
                    zip_code=cust_data.get("zip_code") or None,
                    gps=cust_data.get("gps") or None,
                    # Classification
                    status=status,
                    customer_type=customer_type,
                    billing_type=billing_type,
                    pop_id=pop_id,
                    # Network/Infrastructure
                    base_station=base_station,
                    building_type=building_type,
                    # Account info
                    account_number=cust_data.get("login"),
                    vat_id=vat_id,
                    zoho_id=zoho_id,
                    # Financial
                    mrr=mrr,
                    daily_prepaid_cost=daily_cost,
                    # Partner
                    partner_id=cust_data.get("partner_id"),
                    # Dates
                    signup_date=_parse_date(cust_data.get("date_add")),
                    conversion_date=_parse_date(cust_data.get("conversion_date")),
                    last_online=_parse_datetime(cust_data.get("last_online")),
                    # Attribution
                    added_by=cust_data.get("added_by"),
                    added_by_id=cust_data.get("added_by_id"),
                    referrer=referrer,
                    # Labels
                    labels=labels,
                )

                sync_client.db.add(customer)
                sync_client.increment_created()

            # Commit in batches to reduce transaction size
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("customers_batch_committed", processed=i, total=len(customers))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info("splynx_customers_synced", created=sync_client.current_sync_log.records_created, updated=sync_client.current_sync_log.records_updated)

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
