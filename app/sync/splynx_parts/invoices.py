from datetime import datetime
import structlog
import httpx

from app.models.invoice import Invoice, InvoiceStatus, InvoiceSource
from app.models.customer import Customer
from app.sync.splynx_parts.utils import parse_date

logger = structlog.get_logger()


async def sync_invoices(sync_client, client: httpx.AsyncClient, full_sync: bool):
    """Sync invoices from Splynx. Falls back to proforma invoices when needed."""
    sync_client.start_sync("invoices", "full" if full_sync else "incremental")
    batch_size = 500

    try:
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

        # Pre-fetch customers for faster lookup
        customers_by_splynx_id = {
            c.splynx_id: c.id
            for c in sync_client.db.query(Customer).all()
        }

        for i, inv_data in enumerate(invoices, 1):
            splynx_id = inv_data.get("id")
            existing = sync_client.db.query(Invoice).filter(
                Invoice.splynx_id == splynx_id,
                Invoice.source == InvoiceSource.SPLYNX,
            ).first()

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
        sync_client.complete_sync()
        logger.info("splynx_invoices_synced", created=sync_client.current_sync_log.records_created, updated=sync_client.current_sync_log.records_updated)

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
