from datetime import datetime
import structlog

from app.models.credit_note import CreditNote, CreditNoteStatus
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceSource
from app.sync.splynx_parts.utils import parse_date

logger = structlog.get_logger()


async def sync_credit_notes(sync_client, client, full_sync: bool):
    """Sync credit notes from Splynx."""
    sync_client.start_sync("credit_notes", "full" if full_sync else "incremental")
    batch_size = 500

    try:
        credit_notes = await sync_client._fetch_paginated(client, "/admin/finance/credit-notes")
        logger.info("splynx_credit_notes_fetched", count=len(credit_notes))

        customers_by_splynx_id = {
            c.splynx_id: c.id
            for c in sync_client.db.query(Customer).all()
        }
        invoices_by_splynx_id = {
            inv.splynx_id: inv.id
            for inv in sync_client.db.query(Invoice).filter(Invoice.source == InvoiceSource.SPLYNX).all()
        }

        for i, note in enumerate(credit_notes, 1):
            splynx_id = note.get("id")
            existing = sync_client.db.query(CreditNote).filter(CreditNote.splynx_id == splynx_id).first()

            customer_id = customers_by_splynx_id.get(note.get("customer_id"))
            invoice_id = invoices_by_splynx_id.get(note.get("invoice_id")) if note.get("invoice_id") else None

            amount = float(note.get("amount", note.get("total", 0)) or 0)
            currency = note.get("currency", "NGN")
            credit_number = note.get("number", note.get("credit_number"))

            status_str = str(note.get("status", "")).lower()
            status_map = {
                "draft": CreditNoteStatus.DRAFT,
                "issued": CreditNoteStatus.ISSUED,
                "applied": CreditNoteStatus.APPLIED,
                "cancelled": CreditNoteStatus.CANCELLED,
                "canceled": CreditNoteStatus.CANCELLED,
            }
            status = status_map.get(status_str, CreditNoteStatus.ISSUED)

            issue_date = parse_date(note.get("date_created") or note.get("date"))
            applied_date = parse_date(note.get("date_applied") or note.get("date_payment"))

            if existing:
                existing.customer_id = customer_id
                existing.invoice_id = invoice_id
                existing.credit_number = credit_number
                existing.amount = amount
                existing.currency = currency
                existing.status = status
                existing.issue_date = issue_date
                existing.applied_date = applied_date
                existing.description = note.get("comment") or note.get("description")
                existing.last_synced_at = datetime.utcnow()
                sync_client.increment_updated()
            else:
                credit = CreditNote(
                    splynx_id=splynx_id,
                    customer_id=customer_id,
                    invoice_id=invoice_id,
                    credit_number=credit_number,
                    amount=amount,
                    currency=currency,
                    status=status,
                    issue_date=issue_date,
                    applied_date=applied_date,
                    description=note.get("comment") or note.get("description"),
                )
                sync_client.db.add(credit)
                sync_client.increment_created()

            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("credit_notes_batch_committed", processed=i, total=len(credit_notes))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info(
            "splynx_credit_notes_synced",
            created=sync_client.current_sync_log.records_created,
            updated=sync_client.current_sync_log.records_updated,
        )

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
