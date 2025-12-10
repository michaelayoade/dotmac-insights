from datetime import datetime
import structlog

from app.models.customer_note import CustomerNote
from app.models.customer import Customer
from app.config import settings

logger = structlog.get_logger()


async def sync_customer_notes(sync_client, client, full_sync: bool):
    """Sync customer notes from Splynx."""
    sync_client.start_sync("customer_notes", "full" if full_sync else "incremental")
    batch_size = settings.sync_batch_size

    try:
        notes = await sync_client._fetch_paginated(client, "/admin/customers/customer-notes")
        logger.info("splynx_customer_notes_fetched", count=len(notes))

        # Pre-fetch customers for FK lookup
        customers_by_splynx_id = {
            c.splynx_id: c.id
            for c in sync_client.db.query(Customer).filter(Customer.splynx_id.isnot(None)).all()
        }

        for i, note_data in enumerate(notes, 1):
            splynx_id = note_data.get("id")
            existing = sync_client.db.query(CustomerNote).filter(
                CustomerNote.splynx_id == splynx_id
            ).first()

            # Find customer
            customer_splynx_id = note_data.get("customer_id")
            customer_id = customers_by_splynx_id.get(customer_splynx_id) if customer_splynx_id else None

            # Parse datetime
            note_datetime = None
            if note_data.get("datetime"):
                try:
                    note_datetime = datetime.strptime(note_data["datetime"], "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass

            # Parse pinned_date
            pinned_date = None
            if note_data.get("pinned_date") and note_data.get("pinned_date") not in ["", "0000-00-00"]:
                try:
                    pinned_date = datetime.strptime(note_data["pinned_date"], "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    try:
                        pinned_date = datetime.strptime(note_data["pinned_date"], "%Y-%m-%d")
                    except (ValueError, TypeError):
                        pass

            # Parse scheduled_send_time
            scheduled_send_time = None
            if note_data.get("scheduled_send_time"):
                try:
                    scheduled_send_time = datetime.strptime(
                        note_data["scheduled_send_time"], "%Y-%m-%d %H:%M:%S"
                    )
                except (ValueError, TypeError):
                    pass

            if existing:
                existing.customer_id = customer_id
                existing.splynx_customer_id = customer_splynx_id
                existing.administrator_id = note_data.get("administrator_id")
                existing.note_type = note_data.get("type")
                existing.note_class = note_data.get("class")
                existing.title = note_data.get("title")
                existing.comment = note_data.get("comment")
                existing.assigned_to = note_data.get("assigned_to")
                existing.is_done = note_data.get("is_done") == "1"
                existing.is_sent = note_data.get("is_send") == "1"
                existing.is_pinned = note_data.get("is_pinned") == "1"
                existing.pinned_date = pinned_date
                existing.scheduled_send_time = scheduled_send_time
                existing.note_datetime = note_datetime
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                note = CustomerNote(
                    splynx_id=splynx_id,
                    customer_id=customer_id,
                    splynx_customer_id=customer_splynx_id,
                    administrator_id=note_data.get("administrator_id"),
                    note_type=note_data.get("type"),
                    note_class=note_data.get("class"),
                    title=note_data.get("title"),
                    comment=note_data.get("comment"),
                    assigned_to=note_data.get("assigned_to"),
                    is_done=note_data.get("is_done") == "1",
                    is_sent=note_data.get("is_send") == "1",
                    is_pinned=note_data.get("is_pinned") == "1",
                    pinned_date=pinned_date,
                    scheduled_send_time=scheduled_send_time,
                    note_datetime=note_datetime,
                )
                sync_client.db.add(note)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("customer_notes_batch_committed", processed=i, total=len(notes))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_customer_notes_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
