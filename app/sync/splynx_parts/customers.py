from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple, Any, Dict
import structlog
import bcrypt

from app.models.customer import Customer, CustomerStatus, CustomerType, BillingType
from app.models.pop import Pop
from app.config import settings
from app.models.sync_cursor import parse_datetime
from app.utils.address_normalizer import normalize_address

logger = structlog.get_logger()


def _hash_password(password: str) -> Optional[str]:
    """Hash a password using bcrypt. Returns None if password is empty."""
    if not password:
        return None
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def _fetch_customer_password(sync_client, client, splynx_id: int) -> Optional[str]:
    """Fetch individual customer to get password (not included in bulk list)."""
    try:
        response = await sync_client._request(
            client, "GET", f"/admin/customers/customer/{splynx_id}"
        )
        if response and isinstance(response, dict):
            password = response.get("password")
            return password if isinstance(password, str) else None
    except Exception as e:
        logger.debug("password_fetch_failed", splynx_id=splynx_id, error=str(e))
    return None


async def _fetch_passwords_batch(sync_client, client, splynx_ids: list) -> dict:
    """Fetch passwords for multiple customers concurrently."""
    import asyncio

    async def fetch_one(sid):
        try:
            response = await sync_client._request(
                client, "GET", f"/admin/customers/customer/{sid}"
            )
            if response and isinstance(response, dict):
                return (sid, response.get("password"))
        except Exception:
            pass
        return (sid, None)

    results = await asyncio.gather(*[fetch_one(sid) for sid in splynx_ids])
    return {sid: pwd for sid, pwd in results if pwd}


async def _fetch_billing_info(sync_client, client, splynx_id: int) -> Optional[dict]:
    """Fetch customer billing info (blocking date, deposit, days left)."""
    try:
        response = await sync_client._request(
            client, "GET", f"/admin/customers/billing-info/{splynx_id}"
        )
        if response and isinstance(response, dict):
            return {
                "blocking_date": response.get("blocking_date"),
                "days_until_blocking": response.get("howManyDaysLeft"),
                "months_until_blocking": response.get("howManyMonthsLeft"),
                "deposit_balance": response.get("deposit"),
                "payment_per_month": response.get("paymentPerMonth"),
            }
    except Exception as e:
        logger.debug("billing_info_fetch_failed", splynx_id=splynx_id, error=str(e))
    return None


async def _fetch_first_activation(sync_client, client, splynx_id: int) -> Optional[datetime]:
    """Fetch customer's first activation date from logs."""
    try:
        response = await sync_client._request(
            client, "GET", f"/admin/customers/customer/{splynx_id}/logs-changes--first-activation"
        )
        if response and isinstance(response, dict):
            date_str = response.get("date")
            time_str = response.get("time", "00:00:00")
            if date_str and date_str != "0000-00-00":
                try:
                    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception as e:
        logger.debug("first_activation_fetch_failed", splynx_id=splynx_id, error=str(e))
    return None


async def _fetch_customer_details_batch(sync_client, client, splynx_ids: list) -> dict:
    """
    Fetch password, billing info, and first activation for multiple customers concurrently.
    Returns: {splynx_id: {"password": str, "billing_info": dict, "activation_date": datetime}}
    """
    import asyncio

    async def fetch_one(sid):
        result = {"password": None, "billing_info": None, "activation_date": None}
        try:
            # Fetch all 3 endpoints concurrently for this customer
            customer_resp, billing_resp, activation_resp = await asyncio.gather(
                sync_client._request(client, "GET", f"/admin/customers/customer/{sid}"),
                sync_client._request(client, "GET", f"/admin/customers/billing-info/{sid}"),
                sync_client._request(client, "GET", f"/admin/customers/customer/{sid}/logs-changes--first-activation"),
                return_exceptions=True
            )

            # Password from customer endpoint
            if isinstance(customer_resp, dict):
                result["password"] = customer_resp.get("password")

            # Billing info
            if isinstance(billing_resp, dict):
                result["billing_info"] = {
                    "blocking_date": billing_resp.get("blocking_date"),
                    "days_until_blocking": billing_resp.get("howManyDaysLeft"),
                    "deposit_balance": billing_resp.get("deposit"),
                    "payment_per_month": billing_resp.get("paymentPerMonth"),
                }

            # First activation date
            if isinstance(activation_resp, dict):
                date_str = activation_resp.get("date")
                time_str = activation_resp.get("time", "00:00:00")
                if date_str and date_str != "0000-00-00":
                    try:
                        result["activation_date"] = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        try:
                            result["activation_date"] = datetime.strptime(date_str, "%Y-%m-%d")
                        except ValueError:
                            pass

        except Exception as e:
            logger.debug("customer_details_fetch_failed", splynx_id=sid, error=str(e))

        return (sid, result)

    results = await asyncio.gather(*[fetch_one(sid) for sid in splynx_ids])
    return {sid: data for sid, data in results}


def _parse_date(date_str: str, fmt: str = "%Y-%m-%d") -> datetime | None:
    """Parse date string to datetime, return None if invalid."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, fmt)
    except (ValueError, TypeError):
        return None


def _parse_datetime_str(dt_str: str) -> datetime | None:
    """Parse datetime string (YYYY-MM-DD HH:MM:SS) to datetime."""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _parse_gps(gps_str: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Parse GPS string to latitude and longitude.

    Handles common formats:
    - "lat,lng" (e.g., "6.5244,3.3792")
    - "lat, lng" (with spaces)
    - "(lat, lng)" (with parentheses)
    - Empty or invalid strings

    Returns:
        Tuple of (latitude, longitude), or (None, None) if parsing fails.
    """
    if not gps_str or not isinstance(gps_str, str):
        return None, None

    # Clean up the string
    gps_clean = gps_str.strip().strip("()").strip()

    if not gps_clean:
        return None, None

    try:
        # Split by comma
        parts = [p.strip() for p in gps_clean.split(",")]
        if len(parts) != 2:
            return None, None

        lat = float(parts[0])
        lng = float(parts[1])

        # Validate ranges (Nigeria is roughly lat 4-14, lng 2-15)
        # But we allow wider range for flexibility
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            logger.warning("gps_coordinates_out_of_range", gps=gps_str, lat=lat, lng=lng)
            return None, None

        return lat, lng
    except (ValueError, TypeError, IndexError) as e:
        logger.debug("gps_parse_failed", gps=gps_str, error=str(e))
        return None, None


def _normalize_customer_address(cust_data: dict, current_lat: Optional[float] = None, current_lng: Optional[float] = None) -> dict:
    """Normalize customer address fields from Splynx data.

    Returns dict with normalized city, state, and optionally extracted GPS coordinates.
    """
    raw_city = cust_data.get("city") or None
    raw_state = cust_data.get("state") or cust_data.get("region") or None

    result = normalize_address(raw_city, raw_state, current_lat, current_lng)

    return {
        "city": result["city"],
        "state": result["state"],
        "latitude": result["latitude"],  # Only set if extracted from city field
        "longitude": result["longitude"],
    }


async def sync_customers(sync_client, client, full_sync: bool):
    """Sync customers from Splynx with incremental cursor support.

    Uses last_update field from Splynx API for client-side filtering during incremental syncs.
    """
    sync_client.start_sync("customers", "full" if full_sync else "incremental")
    batch_size = settings.sync_batch_size_customers

    try:
        # Get cursor for incremental sync
        cursor = sync_client.get_cursor("customers")
        last_sync_time: Optional[datetime] = None

        if not full_sync and cursor and cursor.last_modified_at:
            last_sync_time = cursor.last_modified_at  # Now a datetime
            logger.info("splynx_incremental_sync", entity="customers", since=last_sync_time.isoformat() if last_sync_time else None)

        if full_sync:
            sync_client.reset_cursor("customers")

        customers = await sync_client._fetch_paginated(client, "/admin/customers/customer")
        logger.info("splynx_customers_fetched", count=len(customers))

        # Track the latest update time for cursor (as datetime)
        latest_update: Optional[datetime] = None

        # Pre-fetch all POPs for faster lookup
        pops_by_splynx_id = {
            pop.splynx_id: pop.id
            for pop in sync_client.db.query(Pop).all()
        }

        # Pre-fetch customer details concurrently in batches (bulk API doesn't return password, billing info, activation)
        # Each customer requires 3 API calls: /customer/{id}, /billing-info/{id}, /customer/{id}/logs-changes--first-activation
        all_splynx_ids = [c.get("id") for c in customers if c.get("id")]
        customer_details_map = {}
        DETAILS_BATCH_SIZE = 10  # 10 customers x 3 endpoints = 30 concurrent requests per batch
        logger.info("splynx_details_prefetch_start", total=len(all_splynx_ids), batch_size=DETAILS_BATCH_SIZE)
        for batch_start in range(0, len(all_splynx_ids), DETAILS_BATCH_SIZE):
            batch_ids = all_splynx_ids[batch_start:batch_start + DETAILS_BATCH_SIZE]
            batch_details = await _fetch_customer_details_batch(sync_client, client, batch_ids)
            customer_details_map.update(batch_details)
            if batch_start % 500 == 0:
                logger.debug("splynx_details_batch_done", fetched=len(customer_details_map), processed=batch_start + len(batch_ids))
        logger.info("splynx_details_prefetch_done", total_customers=len(customer_details_map))

        processed_count = 0
        skipped_count = 0
        for i, cust_data in enumerate(customers, 1):
            # Track latest update time for cursor (parse to datetime for proper comparison)
            record_update_str = cust_data.get("last_update")
            record_update_dt = parse_datetime(record_update_str) if record_update_str else None

            if record_update_dt:
                if latest_update is None or record_update_dt > latest_update:
                    latest_update = record_update_dt

            # Skip records not modified since last sync (incremental optimization)
            if last_sync_time and record_update_dt and record_update_dt <= last_sync_time:
                skipped_count += 1
                continue

            splynx_id = cust_data.get("id")
            existing = sync_client.db.query(Customer).filter(Customer.splynx_id == splynx_id).first()
            processed_count += 1

            # Map Splynx status to our status
            splynx_status = str(cust_data.get("status", "active")).lower()
            # Map Splynx statuses to internal enum
            status_map = {
                "active": CustomerStatus.ACTIVE,
                "disabled": CustomerStatus.INACTIVE,  # Splynx "disabled" → INACTIVE
                "blocked": CustomerStatus.SUSPENDED,
                "new": CustomerStatus.PROSPECT,
            }
            status = status_map.get(splynx_status, CustomerStatus.INACTIVE)

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

            # Parse GPS coordinates
            gps_raw = cust_data.get("gps") or None
            latitude, longitude = _parse_gps(gps_raw)

            if existing:
                # Basic info
                existing.name = cust_data.get("name", "")
                existing.email = cust_data.get("email") or None
                existing.billing_email = cust_data.get("billing_email") or None
                existing.phone = cust_data.get("phone") or None

                # Normalize address (city, state) - handles FCT/Abuja variations, etc.
                addr = _normalize_customer_address(cust_data, latitude, longitude)

                # Address
                existing.address = cust_data.get("street_1") or None
                existing.address_2 = cust_data.get("street_2") or None
                existing.city = addr["city"]
                existing.state = addr["state"]
                existing.zip_code = cust_data.get("zip_code") or None
                existing.country = cust_data.get("country") or "Nigeria"

                # Geolocation - use GPS from source, or extracted from city field if available
                existing.gps = gps_raw
                existing.latitude = latitude or addr["latitude"]
                existing.longitude = longitude or addr["longitude"]

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
                existing.last_online = _parse_datetime_str(cust_data.get("last_online"))

                # Attribution
                existing.added_by = cust_data.get("added_by")
                existing.added_by_id = cust_data.get("added_by_id")
                existing.referrer = referrer

                # Labels
                existing.labels = labels

                # Details from pre-fetched map (bulk API doesn't return password, billing info, activation)
                details = customer_details_map.get(splynx_id, {})

                # Password
                password_raw = details.get("password")
                if password_raw:
                    existing.password_hash = _hash_password(password_raw)

                # Billing info (blocking date, deposit, etc.)
                billing_info = details.get("billing_info")
                if billing_info:
                    blocking_date_str = billing_info.get("blocking_date")
                    if blocking_date_str and blocking_date_str != "0000-00-00":
                        existing.blocking_date = _parse_date(blocking_date_str)
                    existing.days_until_blocking = billing_info.get("days_until_blocking")
                    if billing_info.get("deposit_balance"):
                        try:
                            existing.deposit_balance = Decimal(str(billing_info["deposit_balance"]))
                        except (ValueError, TypeError):
                            pass
                    if billing_info.get("payment_per_month"):
                        try:
                            existing.payment_per_month = Decimal(str(billing_info["payment_per_month"]))
                        except (ValueError, TypeError):
                            pass

                # First activation date
                activation_date = details.get("activation_date")
                if activation_date:
                    existing.activation_date = activation_date

                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                # Normalize address for new customers
                addr = _normalize_customer_address(cust_data, latitude, longitude)

                customer = Customer(
                    splynx_id=splynx_id,
                    # Basic info
                    name=cust_data.get("name", ""),
                    email=cust_data.get("email") or None,
                    billing_email=cust_data.get("billing_email") or None,
                    phone=cust_data.get("phone") or None,
                    # Address (normalized)
                    address=cust_data.get("street_1") or None,
                    address_2=cust_data.get("street_2") or None,
                    city=addr["city"],
                    state=addr["state"],
                    zip_code=cust_data.get("zip_code") or None,
                    country=cust_data.get("country") or "Nigeria",
                    # Geolocation - use GPS from source, or extracted from city field
                    gps=gps_raw,
                    latitude=latitude or addr["latitude"],
                    longitude=longitude or addr["longitude"],
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
                    last_online=_parse_datetime_str(cust_data.get("last_online")),
                    # Attribution
                    added_by=cust_data.get("added_by"),
                    added_by_id=cust_data.get("added_by_id"),
                    referrer=referrer,
                    # Labels
                    labels=labels,
                )

                # Details from pre-fetched map (bulk API doesn't return password, billing info, activation)
                details = customer_details_map.get(splynx_id, {})

                # Password
                password_raw = details.get("password")
                if password_raw:
                    customer.password_hash = _hash_password(password_raw)

                # Billing info
                billing_info = details.get("billing_info")
                if billing_info:
                    blocking_date_str = billing_info.get("blocking_date")
                    if blocking_date_str and blocking_date_str != "0000-00-00":
                        customer.blocking_date = _parse_date(blocking_date_str)
                    customer.days_until_blocking = billing_info.get("days_until_blocking")
                    if billing_info.get("deposit_balance"):
                        try:
                            customer.deposit_balance = Decimal(str(billing_info["deposit_balance"]))
                        except (ValueError, TypeError):
                            pass
                    if billing_info.get("payment_per_month"):
                        try:
                            customer.payment_per_month = Decimal(str(billing_info["payment_per_month"]))
                        except (ValueError, TypeError):
                            pass

                # First activation date
                activation_date = details.get("activation_date")
                if activation_date:
                    customer.activation_date = activation_date

                sync_client.db.add(customer)
                sync_client.increment_created()

            # Commit in batches to reduce transaction size
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("customers_batch_committed", processed=i, total=len(customers))

        sync_client.db.commit()

        # Update cursor with latest modification time for next incremental sync
        if latest_update:
            sync_client.update_cursor(
                entity_type="customers",
                modified_at=latest_update,
                records_count=processed_count,
            )

        sync_client.complete_sync()
        logger.info(
            "splynx_customers_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
            processed=processed_count,
            skipped=skipped_count,
            cursor_updated_to=latest_update.isoformat() if latest_update else None,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
