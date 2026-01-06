from datetime import datetime, timezone
import structlog

from app.models.administrator import Administrator
from app.models.party import Party, PartyExternalId, PartyRole, PartyType
from app.config import settings

logger = structlog.get_logger()


async def sync_administrators(sync_client, client, full_sync: bool):
    """Sync administrators from Splynx."""
    sync_client.start_sync("administrators", "full" if full_sync else "incremental")
    batch_size = settings.sync_batch_size

    try:
        admins = await sync_client._fetch_paginated(
            client, "/admin/administration/administrators"
        )
        logger.info("splynx_administrators_fetched", count=len(admins))

        party_exts = (
            sync_client.db.query(PartyExternalId)
            .filter(
                PartyExternalId.system == "splynx_admin",
                PartyExternalId.external_key_type == "admin_id",
            )
            .all()
        )
        party_by_ext = {p.external_id: p.party_id for p in party_exts}
        party_email_index = {
            (p.primary_email or "").lower(): p
            for p in sync_client.db.query(Party).filter(Party.primary_email.isnot(None)).all()
        }

        for i, admin_data in enumerate(admins, 1):
            splynx_id = admin_data.get("id")
            existing = sync_client.db.query(Administrator).filter(
                Administrator.splynx_id == splynx_id
            ).first()

            # Parse last activity datetime
            last_activity = None
            if admin_data.get("last_dt"):
                try:
                    last_activity = datetime.strptime(admin_data["last_dt"], "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass

            # Link or create party for this administrator
            party = None
            if splynx_id is not None:
                party_id = party_by_ext.get(str(splynx_id))
                if party_id:
                    party = sync_client.db.query(Party).get(party_id)

            email = (admin_data.get("email") or "").strip().lower()
            if not party and email:
                party = party_email_index.get(email)

            if not party:
                party = Party(
                    type=PartyType.PERSON.value,
                    name=admin_data.get("name") or None,
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

            phone = admin_data.get("phone") or None
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
                party.name = admin_data.get("name") or party.name

            if splynx_id is not None and str(splynx_id) not in party_by_ext:
                sync_client.db.add(
                    PartyExternalId(
                        party_id=party.id,
                        system="splynx_admin",
                        external_id=str(splynx_id),
                        external_key_type="admin_id",
                    )
                )
                party_by_ext[str(splynx_id)] = party.id

            role_name = (admin_data.get("role_name") or "").lower()
            role_code = "admin" if "admin" in role_name else "user"
            has_role = (
                sync_client.db.query(PartyRole)
                .filter(PartyRole.party_id == party.id, PartyRole.role == role_code, PartyRole.until.is_(None))
                .first()
            )
            if not has_role:
                sync_client.db.add(PartyRole(party_id=party.id, role=role_code))

            if existing:
                existing.login = admin_data.get("login")
                existing.name = admin_data.get("name")
                existing.email = admin_data.get("email")
                existing.phone = admin_data.get("phone")
                existing.role_name = admin_data.get("role_name")
                existing.router_access = admin_data.get("router_access")
                existing.partner_id = admin_data.get("partner_id")
                existing.last_ip = admin_data.get("last_ip")
                existing.last_activity = last_activity
                existing.calendar_color = admin_data.get("calendar_color")
                existing.send_from_my_name = admin_data.get("send_from_my_name")
                existing.party_id = party.id
                existing.last_synced_at = datetime.now(timezone.utc)
                sync_client.increment_updated()
            else:
                admin = Administrator(
                    splynx_id=splynx_id,
                    login=admin_data.get("login"),
                    name=admin_data.get("name"),
                    email=admin_data.get("email"),
                    phone=admin_data.get("phone"),
                    role_name=admin_data.get("role_name"),
                    router_access=admin_data.get("router_access"),
                    partner_id=admin_data.get("partner_id"),
                    last_ip=admin_data.get("last_ip"),
                    last_activity=last_activity,
                    calendar_color=admin_data.get("calendar_color"),
                    send_from_my_name=admin_data.get("send_from_my_name"),
                    party_id=party.id,
                )
                sync_client.db.add(admin)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("administrators_batch_committed", processed=i, total=len(admins))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_administrators_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
