"""
Billing Outbound Sync Service

Handles synchronization of Invoice and Payment data to external systems
(ERPNext) with idempotency checking to prevent duplicate updates.

Usage:
    from app.services.billing_outbound_sync import BillingOutboundSyncService

    sync_service = BillingOutboundSyncService(db)
    sync_service.sync_invoice_to_erpnext(invoice)
    sync_service.sync_payment_to_erpnext(payment)
"""
import hashlib
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.outbound_sync import (
    OutboundSyncLog, SyncStatus, SyncOperation, TargetSystem
)
from app.feature_flags import feature_flags
from app.middleware.metrics import record_outbound_sync

logger = logging.getLogger(__name__)


class BillingOutboundSyncService:
    """
    Service for syncing Invoice and Payment to ERPNext.

    Implements idempotency by:
    1. Computing hash of payload before sending
    2. Comparing to stored hash on entity
    3. Skipping sync if unchanged
    4. Storing sync log for audit trail
    """

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def sync_invoice_to_erpnext(self, invoice: Invoice) -> OutboundSyncLog:
        """
        Sync an Invoice to ERPNext.

        Uses idempotency to skip unchanged invoices.

        Returns:
            OutboundSyncLog entry for the operation
        """
        if not feature_flags.BILLING_OUTBOUND_SYNC_ENABLED:
            logger.debug(f"Billing outbound sync disabled, skipping invoice {invoice.id}")
            return self._create_skipped_log(
                "invoice", invoice.id, TargetSystem.ERPNEXT.value,
                "Billing outbound sync disabled"
            )

        # Build payload
        payload = self._build_invoice_payload(invoice)
        payload_hash = self._compute_hash(payload)

        # Idempotency check using erpnext_id presence and hash
        existing_log = self._get_last_successful_sync("invoice", invoice.id, TargetSystem.ERPNEXT.value)
        if existing_log and existing_log.payload_hash == payload_hash:
            logger.info(f"Skipping unchanged invoice {invoice.id} for ERPNext sync")
            return self._create_skipped_log(
                "invoice", invoice.id, TargetSystem.ERPNEXT.value,
                "No changes detected"
            )

        # Determine operation
        operation = SyncOperation.UPDATE.value if invoice.erpnext_id else SyncOperation.CREATE.value

        # Create log entry
        idempotency_key = f"erpnext:invoice:{invoice.id}:{invoice.updated_at.timestamp() if invoice.updated_at else datetime.utcnow().timestamp()}"
        log = OutboundSyncLog.create_pending(
            entity_type="invoice",
            entity_id=invoice.id,
            target_system=TargetSystem.ERPNEXT.value,
            operation=operation,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            request_payload=payload,
        )
        self.db.add(log)

        try:
            if feature_flags.BILLING_OUTBOUND_DRY_RUN:
                logger.info(f"DRY RUN: Would sync invoice {invoice.id} to ERPNext: {operation}")
                log.mark_success(external_id=None, response={"dry_run": True})
            else:
                # Actual ERPNext API call would go here
                # For now, just mark as successful with placeholder
                external_id = self._push_invoice_to_erpnext(invoice, payload, operation)
                log.mark_success(external_id=external_id)
                if external_id:
                    invoice.erpnext_id = external_id

            self.db.flush()
            record_outbound_sync(
                entity_type="invoice",
                target="erpnext",
                success=True,
            )

        except Exception as e:
            logger.exception(f"Failed to sync invoice {invoice.id} to ERPNext")
            log.mark_failed(str(e))
            self.db.flush()
            record_outbound_sync(
                entity_type="invoice",
                target="erpnext",
                success=False,
            )

        return log

    def sync_payment_to_erpnext(self, payment: Payment) -> OutboundSyncLog:
        """
        Sync a Payment to ERPNext.

        Uses idempotency to skip unchanged payments.

        Returns:
            OutboundSyncLog entry for the operation
        """
        if not feature_flags.BILLING_OUTBOUND_SYNC_ENABLED:
            logger.debug(f"Billing outbound sync disabled, skipping payment {payment.id}")
            return self._create_skipped_log(
                "payment", payment.id, TargetSystem.ERPNEXT.value,
                "Billing outbound sync disabled"
            )

        # Build payload
        payload = self._build_payment_payload(payment)
        payload_hash = self._compute_hash(payload)

        # Idempotency check
        existing_log = self._get_last_successful_sync("payment", payment.id, TargetSystem.ERPNEXT.value)
        if existing_log and existing_log.payload_hash == payload_hash:
            logger.info(f"Skipping unchanged payment {payment.id} for ERPNext sync")
            return self._create_skipped_log(
                "payment", payment.id, TargetSystem.ERPNEXT.value,
                "No changes detected"
            )

        # Determine operation
        operation = SyncOperation.UPDATE.value if payment.erpnext_id else SyncOperation.CREATE.value

        # Create log entry
        idempotency_key = f"erpnext:payment:{payment.id}:{payment.updated_at.timestamp() if payment.updated_at else datetime.utcnow().timestamp()}"
        log = OutboundSyncLog.create_pending(
            entity_type="payment",
            entity_id=payment.id,
            target_system=TargetSystem.ERPNEXT.value,
            operation=operation,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            request_payload=payload,
        )
        self.db.add(log)

        try:
            if feature_flags.BILLING_OUTBOUND_DRY_RUN:
                logger.info(f"DRY RUN: Would sync payment {payment.id} to ERPNext: {operation}")
                log.mark_success(external_id=None, response={"dry_run": True})
            else:
                # Actual ERPNext API call would go here
                external_id = self._push_payment_to_erpnext(payment, payload, operation)
                log.mark_success(external_id=external_id)
                if external_id:
                    payment.erpnext_id = external_id

            self.db.flush()
            record_outbound_sync(
                entity_type="payment",
                target="erpnext",
                success=True,
            )

        except Exception as e:
            logger.exception(f"Failed to sync payment {payment.id} to ERPNext")
            log.mark_failed(str(e))
            self.db.flush()
            record_outbound_sync(
                entity_type="payment",
                target="erpnext",
                success=False,
            )

        return log

    # =========================================================================
    # PAYLOAD BUILDERS
    # =========================================================================

    def _build_invoice_payload(self, invoice: Invoice) -> dict:
        """Build ERPNext Sales Invoice payload from Invoice."""
        return {
            "doctype": "Sales Invoice",
            "customer": invoice.customer_id,
            "posting_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "currency": invoice.currency,
            "grand_total": float(invoice.total_amount) if invoice.total_amount else 0,
            "outstanding_amount": float(invoice.balance) if invoice.balance else 0,
            "status": invoice.status.value if invoice.status else None,
            "docstatus": invoice.docstatus,
            # Custom fields for traceability
            "custom_insights_id": invoice.id,
            "custom_invoice_number": invoice.invoice_number,
        }

    def _build_payment_payload(self, payment: Payment) -> dict:
        """Build ERPNext Payment Entry payload from Payment."""
        return {
            "doctype": "Payment Entry",
            "payment_type": "Receive",  # AR payment = receive from customer
            "party_type": "Customer",
            "party": payment.customer_id,
            "posting_date": payment.payment_date.isoformat() if payment.payment_date else None,
            "paid_amount": float(payment.amount) if payment.amount else 0,
            "received_amount": float(payment.base_amount) if payment.base_amount else 0,
            "source_exchange_rate": float(payment.conversion_rate) if payment.conversion_rate else 1,
            "paid_from_account_currency": payment.currency,
            "mode_of_payment": self._map_payment_method(payment.payment_method),
            "reference_no": payment.transaction_reference or payment.receipt_number,
            # Custom fields for traceability
            "custom_insights_id": payment.id,
        }

    def _map_payment_method(self, method) -> str:
        """Map internal payment method to ERPNext mode of payment."""
        if method is None:
            return "Bank Draft"
        mapping = {
            "cash": "Cash",
            "bank_transfer": "Bank Draft",
            "card": "Credit Card",
            "mobile_money": "Mobile Money",
            "paystack": "Paystack",
            "flutterwave": "Flutterwave",
            "other": "Bank Draft",
        }
        return mapping.get(method.value if hasattr(method, 'value') else str(method), "Bank Draft")

    # =========================================================================
    # SYNC OPERATIONS (placeholders for actual API calls)
    # =========================================================================

    def _push_invoice_to_erpnext(self, invoice: Invoice, payload: dict, operation: str) -> Optional[str]:
        """
        Push invoice to ERPNext API.

        Returns:
            External ID (ERPNext document name) if successful
        """
        # TODO: Implement actual ERPNext API call
        # Example:
        # from app.integrations.erpnext import ERPNextClient
        # client = ERPNextClient()
        # if operation == "create":
        #     result = client.create_document("Sales Invoice", payload)
        # else:
        #     result = client.update_document("Sales Invoice", invoice.erpnext_id, payload)
        # return result.get("name")

        logger.info(f"Would push invoice {invoice.id} to ERPNext: {operation}")
        return None

    def _push_payment_to_erpnext(self, payment: Payment, payload: dict, operation: str) -> Optional[str]:
        """
        Push payment to ERPNext API.

        Returns:
            External ID (ERPNext document name) if successful
        """
        # TODO: Implement actual ERPNext API call
        logger.info(f"Would push payment {payment.id} to ERPNext: {operation}")
        return None

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _compute_hash(self, payload: dict) -> str:
        """Compute SHA256 hash of payload for idempotency check."""
        # Sort keys for consistent hashing
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    def _get_last_successful_sync(
        self, entity_type: str, entity_id: int, target_system: str
    ) -> Optional[OutboundSyncLog]:
        """Get the last successful sync log for an entity."""
        return (
            self.db.query(OutboundSyncLog)
            .filter(
                OutboundSyncLog.entity_type == entity_type,
                OutboundSyncLog.entity_id == entity_id,
                OutboundSyncLog.target_system == target_system,
                OutboundSyncLog.status == SyncStatus.SUCCESS.value,
            )
            .order_by(OutboundSyncLog.created_at.desc())
            .first()
        )

    def _create_skipped_log(
        self, entity_type: str, entity_id: int, target_system: str, reason: str
    ) -> OutboundSyncLog:
        """Create a skipped sync log entry (not persisted to DB)."""
        log = OutboundSyncLog(
            entity_type=entity_type,
            entity_id=entity_id,
            target_system=target_system,
            operation=SyncOperation.UPDATE.value,
            status=SyncStatus.SKIPPED.value,
            error_message=reason,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        return log
