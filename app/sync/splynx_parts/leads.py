from datetime import datetime, timezone
import structlog

from app.models.lead import Lead
from app.models.party import Party, PartyExternalId, PartyRole, PartyType
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

        party_exts = (
            sync_client.db.query(PartyExternalId)
            .filter(
                PartyExternalId.system == "splynx",
                PartyExternalId.external_key_type == "lead_id",
            )
            .all()
        )
        party_by_ext = {p.external_id: p.party_id for p in party_exts}
        party_email_index = {
            (p.primary_email or "").lower(): p
            for p in sync_client.db.query(Party).filter(Party.primary_email.isnot(None)).all()
        }

        for i, lead_data in enumerate(leads, 1):
            splynx_id = lead_data.get("id")
            existing = sync_client.db.query(Lead).filter(
                Lead.splynx_id == splynx_id
            ).first()

            # Link or create party for this lead
            party = None
            if splynx_id is not None:
                party_id = party_by_ext.get(str(splynx_id))
                if party_id:
                    party = sync_client.db.query(Party).get(party_id)

            email = (lead_data.get("email") or "").strip().lower()
            if not party and email:
                party = party_email_index.get(email)

            if not party:
                category = str(lead_data.get("category", "")).lower()
                party_type = PartyType.ORGANIZATION.value if category in ["company", "business", "corporate", "enterprise"] else PartyType.PERSON.value
                party = Party(
                    type=party_type,
                    name=lead_data.get("name") or None,
                    emails=[],
                    phones=[],
                )
                sync_client.db.add(party)
                sync_client.db.flush()

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

            phone = lead_data.get("phone") or None
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

            if splynx_id is not None and str(splynx_id) not in party_by_ext:
                sync_client.db.add(
                    PartyExternalId(
                        party_id=party.id,
                        system="splynx",
                        external_id=str(splynx_id),
                        external_key_type="lead_id",
                    )
                )
                party_by_ext[str(splynx_id)] = party.id

            has_lead_role = (
                sync_client.db.query(PartyRole)
                .filter(PartyRole.party_id == party.id, PartyRole.role == "lead", PartyRole.until.is_(None))
                .first()
            )
            if not has_lead_role:
                sync_client.db.add(PartyRole(party_id=party.id, role="lead"))

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
                existing.party_id = party.id
                existing.date_add = parse_datetime(lead_data.get("date_add"))
                existing.last_online = parse_datetime(lead_data.get("last_online"))
                existing.last_update = parse_datetime(lead_data.get("last_update"))
                existing.conversion_date = parse_datetime(lead_data.get("conversion_date"))
                existing.last_synced_at = datetime.now(timezone.utc)
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
                    party_id=party.id,
                    date_add=parse_datetime(lead_data.get("date_add")),
                    last_online=parse_datetime(lead_data.get("last_online")),
                    last_update=parse_datetime(lead_data.get("last_update")),
                    conversion_date=parse_datetime(lead_data.get("conversion_date")),
                    last_synced_at=datetime.now(timezone.utc),
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
