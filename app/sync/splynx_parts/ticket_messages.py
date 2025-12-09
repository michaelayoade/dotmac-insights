from datetime import datetime
import structlog

from app.models.ticket_message import TicketMessage
from app.models.ticket import Ticket
from app.models.customer import Customer
from app.models.administrator import Administrator

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


async def sync_ticket_messages(sync_client, client, full_sync: bool):
    """Sync ticket messages from Splynx."""
    sync_client.start_sync("ticket_messages", "full" if full_sync else "incremental")
    batch_size = 500

    try:
        messages = await sync_client._fetch_paginated(
            client, "/admin/support/ticket-messages"
        )
        logger.info("splynx_ticket_messages_fetched", count=len(messages))

        # Pre-fetch lookup maps for FK resolution
        ticket_map = {}
        tickets = sync_client.db.query(Ticket.id, Ticket.splynx_id).all()
        for t in tickets:
            if t.splynx_id:
                # splynx_id is stored as string in Ticket model
                try:
                    ticket_map[int(t.splynx_id)] = t.id
                except (ValueError, TypeError):
                    pass

        customer_map = {}
        customers = sync_client.db.query(Customer.id, Customer.splynx_id).all()
        for c in customers:
            if c.splynx_id:
                customer_map[c.splynx_id] = c.id

        admin_map = {}
        admins = sync_client.db.query(Administrator.id, Administrator.splynx_id).all()
        for a in admins:
            if a.splynx_id:
                admin_map[a.splynx_id] = a.id

        for i, msg_data in enumerate(messages, 1):
            splynx_id = msg_data.get("id")
            existing = sync_client.db.query(TicketMessage).filter(
                TicketMessage.splynx_id == splynx_id
            ).first()

            # Map foreign keys
            splynx_ticket_id = msg_data.get("ticket_id")
            ticket_id = ticket_map.get(splynx_ticket_id) if splynx_ticket_id else None

            splynx_customer_id = msg_data.get("customer_id")
            customer_id = customer_map.get(splynx_customer_id) if splynx_customer_id else None

            splynx_admin_id = msg_data.get("admin_id")
            admin_id = admin_map.get(splynx_admin_id) if splynx_admin_id else None

            # Determine author type and info
            author_type = None
            if splynx_admin_id:
                author_type = "admin"
            elif splynx_customer_id:
                author_type = "customer"

            # Parse attachments
            attachments = msg_data.get("attachments", [])
            has_attachments = bool(attachments)
            attachments_count = len(attachments) if isinstance(attachments, list) else 0

            if existing:
                existing.ticket_id = ticket_id
                existing.splynx_ticket_id = splynx_ticket_id
                existing.customer_id = customer_id
                existing.splynx_customer_id = splynx_customer_id
                existing.admin_id = admin_id
                existing.splynx_admin_id = splynx_admin_id
                existing.message = msg_data.get("message")
                existing.message_type = msg_data.get("type")
                existing.author_name = msg_data.get("author_name")
                existing.author_email = msg_data.get("author_email")
                existing.author_type = author_type
                existing.has_attachments = has_attachments
                existing.attachments_count = attachments_count
                existing.is_internal = msg_data.get("internal") in (1, "1", True)
                existing.is_read = msg_data.get("is_read") in (1, "1", True)
                existing.created_at = parse_datetime(msg_data.get("created_at")) or existing.created_at
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                message = TicketMessage(
                    splynx_id=splynx_id,
                    ticket_id=ticket_id,
                    splynx_ticket_id=splynx_ticket_id,
                    customer_id=customer_id,
                    splynx_customer_id=splynx_customer_id,
                    admin_id=admin_id,
                    splynx_admin_id=splynx_admin_id,
                    message=msg_data.get("message"),
                    message_type=msg_data.get("type"),
                    author_name=msg_data.get("author_name"),
                    author_email=msg_data.get("author_email"),
                    author_type=author_type,
                    has_attachments=has_attachments,
                    attachments_count=attachments_count,
                    is_internal=msg_data.get("internal") in (1, "1", True),
                    is_read=msg_data.get("is_read") in (1, "1", True),
                    created_at=parse_datetime(msg_data.get("created_at")) or datetime.utcnow(),
                    last_synced_at=datetime.utcnow(),
                )
                sync_client.db.add(message)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("ticket_messages_batch_committed", processed=i, total=len(messages))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_ticket_messages_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
