from datetime import datetime
import structlog

from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketSource
from app.models.customer import Customer

logger = structlog.get_logger()


async def sync_tickets(sync_client, client, full_sync: bool):
    """Sync support tickets from Splynx."""
    sync_client.start_sync("tickets", "full" if full_sync else "incremental")
    batch_size = 500

    try:
        tickets = await sync_client._fetch_paginated(client, "/admin/support/tickets")
        logger.info("splynx_tickets_fetched", count=len(tickets))

        # Pre-fetch customers for FK lookup
        customers_by_splynx_id = {
            c.splynx_id: c.id
            for c in sync_client.db.query(Customer).filter(Customer.splynx_id.isnot(None)).all()
        }

        for i, ticket_data in enumerate(tickets, 1):
            splynx_id = str(ticket_data.get("id"))
            existing = sync_client.db.query(Ticket).filter(
                Ticket.splynx_id == splynx_id
            ).first()

            # Find customer
            customer_splynx_id = ticket_data.get("customer_id")
            customer_id = customers_by_splynx_id.get(customer_splynx_id) if customer_splynx_id else None

            # Map status
            status_id = ticket_data.get("status_id")
            closed = ticket_data.get("closed") == "1"
            if closed:
                status = TicketStatus.CLOSED
            elif status_id == 1:
                status = TicketStatus.OPEN
            elif status_id == 2:
                status = TicketStatus.REPLIED
            elif status_id == 3:
                status = TicketStatus.RESOLVED
            else:
                status = TicketStatus.OPEN

            # Map priority
            priority_str = (ticket_data.get("priority", "") or "").lower()
            priority_map = {
                "low": TicketPriority.LOW,
                "medium": TicketPriority.MEDIUM,
                "high": TicketPriority.HIGH,
                "urgent": TicketPriority.URGENT,
            }
            priority = priority_map.get(priority_str, TicketPriority.MEDIUM)

            # Parse dates
            created_at = None
            if ticket_data.get("created_at"):
                try:
                    created_at = datetime.strptime(ticket_data["created_at"], "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass

            updated_at = None
            if ticket_data.get("updated_at"):
                try:
                    updated_at = datetime.strptime(ticket_data["updated_at"], "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass

            if existing:
                existing.customer_id = customer_id
                existing.subject = ticket_data.get("subject")
                existing.status = status
                existing.priority = priority
                existing.assigned_to = str(ticket_data.get("assign_to")) if ticket_data.get("assign_to") else None
                existing.opening_date = created_at
                existing.resolution_date = updated_at if status in [TicketStatus.RESOLVED, TicketStatus.CLOSED] else None
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                ticket = Ticket(
                    splynx_id=splynx_id,
                    source=TicketSource.SPLYNX,
                    customer_id=customer_id,
                    ticket_number=f"SPL-{splynx_id}",
                    subject=ticket_data.get("subject"),
                    description=ticket_data.get("note"),
                    status=status,
                    priority=priority,
                    assigned_to=str(ticket_data.get("assign_to")) if ticket_data.get("assign_to") else None,
                    opening_date=created_at or datetime.utcnow(),
                    resolution_date=updated_at if status in [TicketStatus.RESOLVED, TicketStatus.CLOSED] else None,
                )
                sync_client.db.add(ticket)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("tickets_batch_committed", processed=i, total=len(tickets))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_tickets_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
