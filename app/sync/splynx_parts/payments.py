from datetime import datetime
import structlog

from app.models.payment import Payment, PaymentMethod, PaymentSource
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceSource

logger = structlog.get_logger()


async def sync_payments(sync_client, client, full_sync: bool):
    """Sync payments from Splynx."""
    sync_client.start_sync("payments", "full" if full_sync else "incremental")
    batch_size = 500

    try:
        payments = await sync_client._fetch_paginated(client, "/admin/finance/payments")
        logger.info("splynx_payments_fetched", count=len(payments))

        # Pre-fetch customers and invoices for faster lookup
        customers_by_splynx_id = {
            c.splynx_id: c.id
            for c in sync_client.db.query(Customer).all()
        }
        invoices_by_splynx_id = {
            inv.splynx_id: inv.id
            for inv in sync_client.db.query(Invoice).filter(Invoice.source == InvoiceSource.SPLYNX).all()
        }

        for i, pay_data in enumerate(payments, 1):
            splynx_id = pay_data.get("id")
            existing = sync_client.db.query(Payment).filter(
                Payment.splynx_id == splynx_id,
                Payment.source == PaymentSource.SPLYNX,
            ).first()

            # Find customer using pre-fetched map
            customer_splynx_id = pay_data.get("customer_id")
            customer_id = customers_by_splynx_id.get(customer_splynx_id)

            # Find invoice using pre-fetched map
            invoice_id = None
            splynx_invoice_id = pay_data.get("invoice_id")
            if splynx_invoice_id:
                invoice_id = invoices_by_splynx_id.get(int(splynx_invoice_id))

            amount = float(pay_data.get("amount", 0) or 0)

            # Map payment_type (integer in Splynx) to method
            payment_type = pay_data.get("payment_type")
            payment_type_map = {
                1: PaymentMethod.CASH,
                2: PaymentMethod.BANK_TRANSFER,
                3: PaymentMethod.CARD,
                4: PaymentMethod.OTHER,
                5: PaymentMethod.PAYSTACK,
                6: PaymentMethod.FLUTTERWAVE,
            }
            payment_method = payment_type_map.get(payment_type, PaymentMethod.OTHER)

            if existing:
                existing.customer_id = customer_id
                existing.invoice_id = invoice_id
                existing.amount = amount
                existing.payment_method = payment_method
                existing.receipt_number = pay_data.get("receipt_number")
                existing.transaction_reference = str(pay_data.get("transaction_id", "")) if pay_data.get("transaction_id") else None
                existing.last_synced_at = datetime.utcnow()

                # Parse date
                if pay_data.get("date"):
                    try:
                        existing.payment_date = datetime.strptime(pay_data["date"], "%Y-%m-%d")
                    except (ValueError, TypeError):
                        pass

                sync_client.increment_updated()
            else:
                payment = Payment(
                    splynx_id=splynx_id,
                    source=PaymentSource.SPLYNX,
                    customer_id=customer_id,
                    invoice_id=invoice_id,
                    amount=amount,
                    payment_method=payment_method,
                    receipt_number=pay_data.get("receipt_number"),
                    transaction_reference=str(pay_data.get("transaction_id", "")) if pay_data.get("transaction_id") else None,
                    payment_date=datetime.utcnow(),
                )

                if pay_data.get("date"):
                    try:
                        payment.payment_date = datetime.strptime(pay_data["date"], "%Y-%m-%d")
                    except (ValueError, TypeError):
                        pass

                sync_client.db.add(payment)
                sync_client.increment_created()

            # Commit in batches
            if i % batch_size == 0:
                sync_client.db.commit()
                logger.debug("payments_batch_committed", processed=i, total=len(payments))

        sync_client.db.commit()
        sync_client.complete_sync()
        logger.info("splynx_payments_synced", created=sync_client.current_sync_log.records_created, updated=sync_client.current_sync_log.records_updated)

    except Exception as e:
        sync_client.db.rollback()
        sync_client.fail_sync(str(e))
        raise
