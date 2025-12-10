from datetime import datetime, timezone
from typing import Optional
import structlog
import httpx

from app.models.invoice import Invoice, InvoiceStatus, InvoiceSource
from app.models.customer import Customer
from app.sync.splynx_parts.utils import parse_date
from app.config import settings
from app.models.sync_cursor import parse_datetime

logger = structlog.get_logger()


async def sync_invoices(sync_client, client: httpx.AsyncClient, full_sync: bool):
    """Sync invoices from Splynx with incremental cursor support.

    Falls back to proforma invoices when needed. Uses date_updated for client-side filtering.
    """
    sync_client.start_sync("invoices", "full" if full_sync else "incremental")
    batch_size = settings.sync_batch_size_invoices

    try:
        # Get cursor for incremental sync
        cursor = sync_client.get_cursor("invoices")
        last_sync_time: Optional[datetime] = None

        if not full_sync and cursor and cursor.last_modified_at:
            last_sync_time = cursor.last_modified_at  # Now a datetime
            logger.info("splynx_incremental_sync", entity="invoices", since=last_sync_time.isoformat() if last_sync_time else None)

        if full_sync:
            sync_client.reset_cursor("invoices")

        # Try regular invoices first, fall back to proforma-invoices
        invoices = []
        try:
            invoices = await sync_client._fetch_paginated(client, "/admin/finance/invoices")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [403, 405, 500]:
                logger.warning("splynx_invoices_endpoint_unavailable", status=e.response.status_code)
                invoices = await sync_client._fetch_paginated(client, "/admin/finance/proforma-invoices")
            else:
                raise
        except Exception:
            logger.warning("splynx_invoices_fallback_to_proforma")
            invoices = await sync_client._fetch_paginated(client, "/admin/finance/proforma-invoices")

        logger.info("splynx_invoices_fetched", count=len(invoices))

        # Track latest update time for cursor (as datetime)
        latest_update: Optional[datetime] = None

        # Pre-fetch customers for faster lookup
        customers_by_splynx_id = {
            c.splynx_id: c.id
            for c in sync_client.db.query(Customer).all()
        }

        processed_count = 0
        skipped_count = 0
        for i, inv_data in enumerate(invoices, 1):
            # Track latest update time for cursor (parse to datetime for proper comparison)
            record_update_str = inv_data.get("date_updated") or inv_data.get("real_create_datetime")
            record_update_dt = parse_datetime(record_update_str) if record_update_str else None

            if record_update_dt:
                if latest_update is None or record_update_dt > latest_update:
                    latest_update = record_update_dt

            # Skip records not modified since last sync (incremental optimization)
            if last_sync_time and record_update_dt and record_update_dt <= last_sync_time:
                skipped_count += 1
                continue

            splynx_id = inv_data.get("id")
            existing = sync_client.db.query(Invoice).filter(
                Invoice.splynx_id == splynx_id,
                Invoice.source == InvoiceSource.SPLYNX,
            ).first()
            processed_count += 1

            # Find customer using pre-fetched map
            customer_splynx_id = inv_data.get("customer_id")
            customer_id = customers_by_splynx_id.get(customer_splynx_id)

            # Determine status
            date_payment = inv_data.get("date_payment")
            splynx_status = str(inv_data.get("status", "")).lower()

            if date_payment and date_payment != "0000-00-00":
                status = InvoiceStatus.PAID
            elif splynx_status in ["paid"]:
                status = InvoiceStatus.PAID
            elif splynx_status in ["cancelled", "canceled"]:
                status = InvoiceStatus.CANCELLED
            elif splynx_status in ["overdue"]:
                status = InvoiceStatus.OVERDUE
            elif splynx_status in ["partially_paid", "partial"]:
                status = InvoiceStatus.PARTIALLY_PAID
            else:
                status = InvoiceStatus.PENDING

            # Amounts
            total_amount = float(inv_data.get("total", inv_data.get("amount_total", 0)) or 0)
            amount_paid = float(inv_data.get("payment_amount", inv_data.get("amount_paid", 0)) or 0)

            # Get invoice number (proforma may not have this)
            invoice_number = inv_data.get("number", inv_data.get("invoice_number", f"PRO-{splynx_id}"))

            if existing:
                existing.customer_id = customer_id
                existing.invoice_number = invoice_number
                existing.total_amount = total_amount
                existing.amount = total_amount
                existing.amount_paid = amount_paid
                existing.balance = total_amount - amount_paid
                existing.status = status
                existing.last_synced_at = datetime.utcnow()

                date_created = inv_data.get("date_created", inv_data.get("real_create_datetime", ""))
                parsed_date = parse_date(date_created)
                if parsed_date:
                    existing.invoice_date = parsed_date

                sync_client.increment_updated()
            else:
                invoice = Invoice(
                    splynx_id=splynx_id,
                    source=InvoiceSource.SPLYNX,
                    customer_id=customer_id,
                    invoice_number=invoice_number,
                    total_amount=total_amount,
                    amount=total_amount,
                    amount_paid=amount_paid,
                    balance=total_amount - amount_paid,
                    status=status,
                    invoice_date=datetime.utcnow(),
                )

                date_created = inv_data.get("date_created", inv_data.get("real_create_datetime", ""))
                parsed_date = parse_date(date_created)
                if parsed_date:
                    invoice.invoice_date = parsed_date

                sync_client.db.add(invoice)
                sync_client.increment_created()

            # Commit in batches
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("invoices_batch_committed", processed=i, total=len(invoices))

        sync_client.db.commit()

        # Update cursor with latest modification time for next incremental sync
        if latest_update:
            sync_client.update_cursor(
                entity_type="invoices",
                modified_at=latest_update,
                records_count=processed_count,
            )

        sync_client.complete_sync()
        logger.info(
            "splynx_invoices_synced",
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
