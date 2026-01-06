from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple, Any, Dict
import structlog
import bcrypt

from app.models.party import (
    CustomerAccount,
    CustomerAccountReseller,
    Party,
    PartyExternalId,
    PartyRole,
    PartyType,
)
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
        party_ext_ids = (
            sync_client.db.query(PartyExternalId)
            .filter(PartyExternalId.system == "splynx")
            .all()
        )
        party_by_ext = {p.external_id: p.party_id for p in party_ext_ids}
        partner_ext_ids = (
            sync_client.db.query(PartyExternalId)
            .filter(PartyExternalId.system == "splynx_partner")
            .all()
        )
        partner_by_ext = {p.external_id: p.party_id for p in partner_ext_ids}
        party_email_index = {
            (p.primary_email or "").lower(): p
            for p in sync_client.db.query(Party).filter(Party.primary_email.isnot(None)).all()
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
            processed_count += 1

            # Map Splynx status to our status
            splynx_status = str(cust_data.get("status", "active")).lower()
            status_map = {
                "active": "active",
                "disabled": "suspended",
                "blocked": "suspended",
                "new": "pending",
            }
            account_status = status_map.get(splynx_status, "active")

            # Find POP if location_id exists (using pre-fetched map)
            pop_id = None
            location_id = cust_data.get("location_id")
            if location_id:
                pop_id = pops_by_splynx_id.get(int(location_id))

            # Map category to party type
            category = str(cust_data.get("category", "")).lower()
            is_business = category in ["company", "business", "corporate", "enterprise"]

            # Map billing type
            billing_type = str(cust_data.get("billing_type", "") or "").lower() or None

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

            # Ensure party-based identity records exist
            party = None
            created = False
            if splynx_id is not None:
                party_id = party_by_ext.get(str(splynx_id))
                if party_id:
                    party = sync_client.db.query(Party).get(party_id)

            email = (cust_data.get("email") or "").strip().lower()
            if not party and email:
                party = party_email_index.get(email)

            if not party:
                party_type = PartyType.ORGANIZATION.value if is_business else PartyType.PERSON.value
                party = Party(
                    type=party_type,
                    name=cust_data.get("name", "") or None,
                    emails=[],
                    phones=[],
                )
                sync_client.db.add(party)
                sync_client.db.flush()
                created = True

            if email:
                emails = list(party.emails or [])
                if not any((e.get("address") or "").lower() == email for e in emails):
                    emails.append(
                        {
                            "address": email,
                            "label": "primary",
                            "is_primary": len(emails) == 0,
                            "verified": False,
                        }
                    )
                    party.emails = emails
                    party_email_index[email] = party

            billing_email = (cust_data.get("billing_email") or "").strip().lower()
            if billing_email and billing_email != email:
                emails = list(party.emails or [])
                if not any((e.get("address") or "").lower() == billing_email for e in emails):
                    emails.append(
                        {
                            "address": billing_email,
                            "label": "billing",
                            "is_primary": len(emails) == 0,
                            "verified": False,
                        }
                    )
                    party.emails = emails

            phone = cust_data.get("phone") or None
            if phone:
                phones = list(party.phones or [])
                if not any((p.get("number") or "") == phone for p in phones):
                    phones.append(
                        {
                            "number": phone,
                            "label": "primary",
                            "is_primary": len(phones) == 0,
                            "can_sms": False,
                            "can_whatsapp": False,
                        }
                    )
                    party.phones = phones

            if not party.name:
                party.name = cust_data.get("name") or party.name

            if splynx_id is not None and str(splynx_id) not in party_by_ext:
                sync_client.db.add(
                    PartyExternalId(
                        party_id=party.id,
                        system="splynx",
                        external_id=str(splynx_id),
                        external_key_type="customer_id",
                    )
                )
                party_by_ext[str(splynx_id)] = party.id

            has_customer_role = (
                sync_client.db.query(PartyRole)
                .filter(PartyRole.party_id == party.id, PartyRole.role == "customer", PartyRole.until.is_(None))
                .first()
            )
            if not has_customer_role:
                sync_client.db.add(PartyRole(party_id=party.id, role="customer"))

            account = (
                sync_client.db.query(CustomerAccount)
                .filter(CustomerAccount.party_id == party.id)
                .first()
            )
            account_status = "active"
            if splynx_status in ["blocked", "disabled"]:
                account_status = "suspended"
            elif splynx_status in ["new"]:
                account_status = "pending"

            if not account:
                account_number = cust_data.get("login") or str(splynx_id)
                account = CustomerAccount(
                    party_id=party.id,
                    account_number=str(account_number),
                    status=account_status,
                    billing_email=cust_data.get("billing_email") or cust_data.get("email"),
                    external_ids={
                        "splynx_id": splynx_id,
                    },
                )
                sync_client.db.add(account)
                created = True
            else:
                account.status = account_status
                if not account.billing_email:
                    account.billing_email = cust_data.get("billing_email") or cust_data.get("email")

            sync_client.db.flush()

            partner_id = cust_data.get("partner_id")
            if partner_id:
                partner_key = str(partner_id)
                reseller_party_id = partner_by_ext.get(partner_key)
                if not reseller_party_id:
                    reseller_party = Party(
                        type=PartyType.ORGANIZATION.value,
                        name=f"Splynx Partner {partner_key}",
                    )
                    sync_client.db.add(reseller_party)
                    sync_client.db.flush()
                    sync_client.db.add(
                        PartyExternalId(
                            party_id=reseller_party.id,
                            system="splynx_partner",
                            external_id=partner_key,
                            external_key_type="partner_id",
                            is_primary=True,
                        )
                    )
                    sync_client.db.add(PartyRole(party_id=reseller_party.id, role="reseller"))
                    partner_by_ext[partner_key] = reseller_party.id
                    reseller_party_id = reseller_party.id

                existing_reseller = (
                    sync_client.db.query(CustomerAccountReseller)
                    .filter(
                        CustomerAccountReseller.account_id == account.id,
                        CustomerAccountReseller.reseller_party_id == reseller_party_id,
                        CustomerAccountReseller.until.is_(None),
                    )
                    .first()
                )
                if not existing_reseller:
                    sync_client.db.add(
                        CustomerAccountReseller(
                            account_id=account.id,
                            reseller_party_id=reseller_party_id,
                        )
                    )

            # Normalize address for party payloads
            addr = _normalize_customer_address(cust_data, latitude, longitude)
            if cust_data.get("name"):
                party.name = cust_data.get("name") or party.name

            # Addresses (replace primary address with latest sync)
            address_line1 = cust_data.get("street_1") or None
            address_line2 = cust_data.get("street_2") or None
            postal_code = cust_data.get("zip_code") or None
            country = cust_data.get("country") or "Nigeria"
            if address_line1 or address_line2 or addr["city"] or addr["state"] or postal_code:
                party.addresses = [
                    {
                        "type": "primary",
                        "line1": address_line1,
                        "line2": address_line2,
                        "city": addr["city"],
                        "state": addr["state"],
                        "postal_code": postal_code,
                        "country": country,
                        "lat": latitude or addr["latitude"],
                        "lng": longitude or addr["longitude"],
                        "is_primary": True,
                    }
                ]

            # Tags from labels
            if labels_list:
                existing_tags = set(party.tags or [])
                party.tags = sorted(existing_tags.union(set(labels_list)))

            # Details from pre-fetched map (bulk API doesn't return password, billing info, activation)
            details = customer_details_map.get(splynx_id, {})
            password_raw = details.get("password")
            billing_info = details.get("billing_info") or {}
            activation_date = details.get("activation_date")

            custom_fields = dict(party.custom_fields or {})
            custom_fields.update(
                {
                    "base_station": base_station,
                    "building_type": building_type,
                    "referrer": referrer,
                    "zoho_id": zoho_id,
                    "vat_id": vat_id,
                    "partner_id": cust_data.get("partner_id"),
                    "pop_id": pop_id,
                    "gps": gps_raw,
                    "signup_date": _parse_date(cust_data.get("date_add")),
                    "conversion_date": _parse_date(cust_data.get("conversion_date")),
                    "last_online": _parse_datetime_str(cust_data.get("last_online")),
                    "added_by": cust_data.get("added_by"),
                    "added_by_id": cust_data.get("added_by_id"),
                    "daily_prepaid_cost": daily_cost,
                }
            )

            if password_raw:
                custom_fields["splynx_password_hash"] = _hash_password(password_raw)

            if billing_info:
                custom_fields["blocking_date"] = _parse_date(billing_info.get("blocking_date"))
                custom_fields["days_until_blocking"] = billing_info.get("days_until_blocking")
                custom_fields["deposit_balance"] = billing_info.get("deposit_balance")
                custom_fields["payment_per_month"] = billing_info.get("payment_per_month")

            party.custom_fields = custom_fields

            # Update account fields from Splynx
            account.account_number = account.account_number or str(cust_data.get("login") or splynx_id)
            account.status = account_status
            account.billing_type = billing_type
            if mrr is not None:
                account.mrr = Decimal(str(mrr))
            if activation_date:
                account.activated_at = activation_date

            account.external_ids = {
                **(account.external_ids or {}),
                "splynx_id": splynx_id,
            }

            if created:
                sync_client.increment_created()
            else:
                sync_client.increment_updated()

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
