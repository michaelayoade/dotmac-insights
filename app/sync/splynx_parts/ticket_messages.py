from datetime import datetime
import structlog

from app.models.ticket_message import TicketMessage
from app.models.ticket import Ticket
from app.models.customer import Customer
from app.models.administrator import Administrator
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


async def sync_ticket_messages(sync_client, client, full_sync: bool):
    """Sync ticket messages from Splynx."""
    sync_client.start_sync("ticket_messages", "full" if full_sync else "incremental")
    batch_size = settings.sync_batch_size_messages

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
        admin_name_map = {}  # splynx_id -> name for author_name population
        admins = sync_client.db.query(Administrator.id, Administrator.splynx_id, Administrator.name).all()
        for a in admins:
            if a.splynx_id:
                admin_map[a.splynx_id] = a.id
                admin_name_map[a.splynx_id] = a.name

        # Also build customer name map
        customer_name_map = {}
        customers_with_names = sync_client.db.query(Customer.splynx_id, Customer.name).filter(
            Customer.splynx_id.isnot(None)
        ).all()
        for c in customers_with_names:
            if c.splynx_id:
                customer_name_map[c.splynx_id] = c.name

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
            author_type = msg_data.get("author_type")  # Use API value: 'admin' or 'customer'
            if not author_type:
                if splynx_admin_id:
                    author_type = "admin"
                elif splynx_customer_id:
                    author_type = "customer"

            # Derive author_name from admin or customer lookup
            author_name = None
            if splynx_admin_id and splynx_admin_id in admin_name_map:
                author_name = admin_name_map[splynx_admin_id]
            elif splynx_customer_id and splynx_customer_id in customer_name_map:
                author_name = customer_name_map[splynx_customer_id]

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
                existing.message_type = msg_data.get("message_type") or msg_data.get("type")
                existing.author_name = author_name
                existing.author_email = msg_data.get("author_email") or msg_data.get("mail_to")
                existing.author_type = author_type
                existing.has_attachments = has_attachments
                existing.attachments_count = attachments_count
                existing.is_internal = msg_data.get("internal") in (1, "1", True) or msg_data.get("hide_for_customer") in (1, "1", True)
                existing.is_read = msg_data.get("is_read") in (1, "1", True)
                # Parse created_at from date + time fields
                date_str = msg_data.get("date")
                time_str = msg_data.get("time")
                if date_str and time_str:
                    existing.created_at = parse_datetime(f"{date_str} {time_str}") or existing.created_at
                elif date_str:
                    existing.created_at = parse_datetime(date_str) or existing.created_at
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
                    message_type=msg_data.get("message_type") or msg_data.get("type"),
                    author_name=author_name,
                    author_email=msg_data.get("author_email") or msg_data.get("mail_to"),
                    author_type=author_type,
                    has_attachments=has_attachments,
                    attachments_count=attachments_count,
                    is_internal=msg_data.get("internal") in (1, "1", True) or msg_data.get("hide_for_customer") in (1, "1", True),
                    is_read=msg_data.get("is_read") in (1, "1", True),
                    created_at=parse_datetime(f"{msg_data.get('date')} {msg_data.get('time')}") if msg_data.get("date") and msg_data.get("time") else parse_datetime(msg_data.get("date")) or datetime.utcnow(),
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
