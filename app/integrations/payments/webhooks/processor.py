"""
Webhook Processor Service

Handles incoming webhooks from payment providers with:
- Signature verification
- Idempotency (deduplication)
- Event routing to appropriate handlers
- Transaction status updates
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, Callable, Awaitable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gateway_transaction import (
    GatewayTransaction,
    GatewayProvider,
    GatewayTransactionStatus,
)
from app.models.transfer import Transfer, TransferStatus
from app.models.webhook_event import WebhookEvent
from app.integrations.payments.enums import PaymentProvider, TransactionStatus
from app.integrations.payments.providers.paystack import PaystackClient
from app.integrations.payments.providers.flutterwave import FlutterwaveClient
from app.integrations.payments.exceptions import WebhookVerificationError

logger = logging.getLogger(__name__)

# Type alias for webhook handlers
WebhookHandler = Callable[[Dict[str, Any], AsyncSession], Awaitable[None]]


class WebhookProcessor:
    """
    Process webhooks from payment providers.

    Features:
    - Signature verification per provider
    - Idempotent processing via WebhookEvent table
    - Event routing based on event type
    - Automatic transaction status updates
    """

    def __init__(self):
        self._paystack_client: Optional[PaystackClient] = None
        self._flutterwave_client: Optional[FlutterwaveClient] = None

        # Custom handlers registered by event type
        self._custom_handlers: Dict[str, list[WebhookHandler]] = {}

    def get_paystack_client(self) -> PaystackClient:
        """Lazy-load Paystack client."""
        if self._paystack_client is None:
            self._paystack_client = PaystackClient()
        return self._paystack_client

    def get_flutterwave_client(self) -> FlutterwaveClient:
        """Lazy-load Flutterwave client."""
        if self._flutterwave_client is None:
            self._flutterwave_client = FlutterwaveClient()
        return self._flutterwave_client

    def register_handler(self, event_type: str, handler: WebhookHandler) -> None:
        """
        Register a custom handler for an event type.

        Args:
            event_type: Event type string (e.g., "charge.success", "transfer.success")
            handler: Async function to handle the event
        """
        if event_type not in self._custom_handlers:
            self._custom_handlers[event_type] = []
        self._custom_handlers[event_type].append(handler)

    # =========================================================================
    # Signature Verification
    # =========================================================================

    def verify_paystack_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Paystack webhook signature."""
        client = self.get_paystack_client()
        return client.verify_webhook_signature(payload, signature)

    def verify_flutterwave_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Flutterwave webhook signature."""
        client = self.get_flutterwave_client()
        return client.verify_webhook_signature(payload, signature)

    # =========================================================================
    # Main Processing Entry Points
    # =========================================================================

    async def process_paystack_webhook(
        self,
        payload: bytes,
        signature: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Process a Paystack webhook.

        Args:
            payload: Raw request body
            signature: x-paystack-signature header
            db: Database session

        Returns:
            Processing result
        """
        # Verify signature
        if not self.verify_paystack_signature(payload, signature):
            raise WebhookVerificationError(
                message="Invalid Paystack webhook signature",
                provider="paystack",
            )

        data = json.loads(payload)
        event_type = data.get("event", "unknown")
        event_data = data.get("data", {})

        return await self._process_event(
            provider=PaymentProvider.PAYSTACK,
            event_type=event_type,
            event_data=event_data,
            raw_payload=data,
            db=db,
        )

    async def process_flutterwave_webhook(
        self,
        payload: bytes,
        signature: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Process a Flutterwave webhook.

        Args:
            payload: Raw request body
            signature: verif-hash header
            db: Database session

        Returns:
            Processing result
        """
        # Verify signature
        if not self.verify_flutterwave_signature(payload, signature):
            raise WebhookVerificationError(
                message="Invalid Flutterwave webhook signature",
                provider="flutterwave",
            )

        data = json.loads(payload)
        event_type = data.get("event", "unknown")
        event_data = data.get("data", {})

        return await self._process_event(
            provider=PaymentProvider.FLUTTERWAVE,
            event_type=event_type,
            event_data=event_data,
            raw_payload=data,
            db=db,
        )

    # =========================================================================
    # Core Processing Logic
    # =========================================================================

    async def _process_event(
        self,
        provider: PaymentProvider,
        event_type: str,
        event_data: Dict[str, Any],
        raw_payload: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Process a webhook event with idempotency.

        Args:
            provider: Payment provider
            event_type: Event type string
            event_data: Event payload data
            raw_payload: Full raw webhook payload
            db: Database session

        Returns:
            Processing result with status
        """
        # Extract idempotency key
        idempotency_key = self._extract_idempotency_key(provider, event_type, event_data)

        # Check for duplicate
        existing = await self._get_existing_event(db, provider.value, idempotency_key)
        if existing:
            logger.info(f"Duplicate webhook ignored: {provider.value}/{idempotency_key}")
            return {
                "status": "duplicate",
                "message": "Event already processed",
                "event_id": existing.id,
            }

        # Create webhook event record
        webhook_event = WebhookEvent(
            provider=provider.value,
            event_type=event_type,
            idempotency_key=idempotency_key,
            payload=raw_payload,
            status="processing",
        )
        db.add(webhook_event)
        await db.flush()

        try:
            # Route to appropriate handler
            await self._route_event(provider, event_type, event_data, db)

            # Run custom handlers
            await self._run_custom_handlers(event_type, event_data, db)

            # Mark as processed
            webhook_event.status = "processed"
            webhook_event.processed_at = datetime.utcnow()
            await db.commit()

            logger.info(f"Webhook processed: {provider.value}/{event_type}/{idempotency_key}")
            return {
                "status": "processed",
                "message": "Event processed successfully",
                "event_id": webhook_event.id,
            }

        except Exception as e:
            logger.error(f"Webhook processing failed: {e}", exc_info=True)
            webhook_event.status = "failed"
            webhook_event.error_message = str(e)
            await db.commit()

            return {
                "status": "failed",
                "message": str(e),
                "event_id": webhook_event.id,
            }

    def _extract_idempotency_key(
        self,
        provider: PaymentProvider,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> str:
        """Extract unique idempotency key from event data."""
        if provider == PaymentProvider.PAYSTACK:
            # Paystack: use reference or id
            ref = event_data.get("reference") or event_data.get("id") or ""
            return f"{event_type}:{ref}"

        elif provider == PaymentProvider.FLUTTERWAVE:
            # Flutterwave: use tx_ref or id
            ref = event_data.get("tx_ref") or event_data.get("id") or ""
            return f"{event_type}:{ref}"

        return f"{event_type}:{hash(json.dumps(event_data, sort_keys=True))}"

    async def _get_existing_event(
        self,
        db: AsyncSession,
        provider: str,
        idempotency_key: str,
    ) -> Optional[WebhookEvent]:
        """Check if event was already processed."""
        result = await db.execute(
            select(WebhookEvent).where(
                WebhookEvent.provider == provider,
                WebhookEvent.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def _route_event(
        self,
        provider: PaymentProvider,
        event_type: str,
        event_data: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Route event to appropriate handler based on type."""
        # Normalize event types across providers
        normalized_type = self._normalize_event_type(provider, event_type)

        handlers = {
            "payment.success": self._handle_payment_success,
            "payment.failed": self._handle_payment_failed,
            "transfer.success": self._handle_transfer_success,
            "transfer.failed": self._handle_transfer_failed,
            "transfer.reversed": self._handle_transfer_reversed,
            "refund.processed": self._handle_refund,
            "virtual_account.credit": self._handle_virtual_account_credit,
        }

        handler = handlers.get(normalized_type)
        if handler:
            await handler(provider, event_data, db)
        else:
            logger.debug(f"No handler for event type: {event_type} -> {normalized_type}")

    def _normalize_event_type(self, provider: PaymentProvider, event_type: str) -> str:
        """Normalize event types across providers."""
        if provider == PaymentProvider.PAYSTACK:
            mapping = {
                "charge.success": "payment.success",
                "charge.failed": "payment.failed",
                "transfer.success": "transfer.success",
                "transfer.failed": "transfer.failed",
                "transfer.reversed": "transfer.reversed",
                "refund.processed": "refund.processed",
                "dedicatedaccount.assign.success": "virtual_account.created",
                "paymentrequest.success": "payment.success",
            }
        elif provider == PaymentProvider.FLUTTERWAVE:
            mapping = {
                "charge.completed": "payment.success",
                "charge.failed": "payment.failed",
                "transfer.completed": "transfer.success",
                "transfer.failed": "transfer.failed",
                "refund.completed": "refund.processed",
            }
        else:
            mapping = {}

        return mapping.get(event_type, event_type)

    async def _run_custom_handlers(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Run any custom handlers registered for this event type."""
        handlers = self._custom_handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(event_data, db)
            except Exception as e:
                logger.error(f"Custom handler failed for {event_type}: {e}")

    # =========================================================================
    # Event Handlers
    # =========================================================================

    async def _handle_payment_success(
        self,
        provider: PaymentProvider,
        event_data: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Handle successful payment webhook."""
        reference = self._get_reference(provider, event_data)
        if not reference:
            return

        # Find and update transaction
        result = await db.execute(
            select(GatewayTransaction).where(
                GatewayTransaction.reference == reference
            )
        )
        transaction = result.scalar_one_or_none()

        if transaction:
            transaction.status = GatewayTransactionStatus.SUCCESS
            transaction.provider_reference = str(event_data.get("id", ""))
            transaction.paid_at = datetime.utcnow()

            # Update fees if provided
            if provider == PaymentProvider.PAYSTACK:
                fees = event_data.get("fees", 0)
                transaction.fees = Decimal(fees) / 100  # Convert from kobo
            elif provider == PaymentProvider.FLUTTERWAVE:
                transaction.fees = Decimal(str(event_data.get("app_fee", 0)))

            # Store authorization for recurring
            auth = event_data.get("authorization") or event_data.get("card")
            if auth:
                transaction.extra_data = transaction.extra_data or {}
                transaction.extra_data["authorization"] = auth

            logger.info(f"Payment marked successful: {reference}")

    async def _handle_payment_failed(
        self,
        provider: PaymentProvider,
        event_data: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Handle failed payment webhook."""
        reference = self._get_reference(provider, event_data)
        if not reference:
            return

        result = await db.execute(
            select(GatewayTransaction).where(
                GatewayTransaction.reference == reference
            )
        )
        transaction = result.scalar_one_or_none()

        if transaction:
            transaction.status = GatewayTransactionStatus.FAILED
            transaction.failure_code = event_data.get("gateway_response", "")
            logger.info(f"Payment marked failed: {reference}")

    async def _handle_transfer_success(
        self,
        provider: PaymentProvider,
        event_data: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Handle successful transfer webhook."""
        reference = self._get_reference(provider, event_data)
        if not reference:
            return

        result = await db.execute(
            select(Transfer).where(Transfer.reference == reference)
        )
        transfer = result.scalar_one_or_none()

        if transfer:
            transfer.status = TransferStatus.SUCCESS
            transfer.provider_reference = str(event_data.get("id", ""))
            transfer.completed_at = datetime.utcnow()
            logger.info(f"Transfer marked successful: {reference}")

    async def _handle_transfer_failed(
        self,
        provider: PaymentProvider,
        event_data: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Handle failed transfer webhook."""
        reference = self._get_reference(provider, event_data)
        if not reference:
            return

        result = await db.execute(
            select(Transfer).where(Transfer.reference == reference)
        )
        transfer = result.scalar_one_or_none()

        if transfer:
            transfer.status = TransferStatus.FAILED
            transfer.failure_reason = event_data.get("reason", "Transfer failed")
            logger.info(f"Transfer marked failed: {reference}")

    async def _handle_transfer_reversed(
        self,
        provider: PaymentProvider,
        event_data: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Handle reversed transfer webhook."""
        reference = self._get_reference(provider, event_data)
        if not reference:
            return

        result = await db.execute(
            select(Transfer).where(Transfer.reference == reference)
        )
        transfer = result.scalar_one_or_none()

        if transfer:
            transfer.status = TransferStatus.REVERSED
            transfer.failure_reason = "Transfer reversed"
            logger.info(f"Transfer marked reversed: {reference}")

    async def _handle_refund(
        self,
        provider: PaymentProvider,
        event_data: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Handle refund processed webhook."""
        # Get original transaction reference
        if provider == PaymentProvider.PAYSTACK:
            transaction_ref = event_data.get("transaction", {}).get("reference")
        else:
            transaction_ref = event_data.get("tx_ref")

        if not transaction_ref:
            return

        result = await db.execute(
            select(GatewayTransaction).where(
                GatewayTransaction.reference == transaction_ref
            )
        )
        transaction = result.scalar_one_or_none()

        if transaction:
            transaction.status = GatewayTransactionStatus.REFUNDED
            transaction.extra_data = transaction.extra_data or {}
            transaction.extra_data["refund"] = event_data
            logger.info(f"Payment marked refunded: {transaction_ref}")

    async def _handle_virtual_account_credit(
        self,
        provider: PaymentProvider,
        event_data: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Handle virtual account credit (payment received)."""
        # This is essentially a payment success via bank transfer
        await self._handle_payment_success(provider, event_data, db)

    def _get_reference(self, provider: PaymentProvider, event_data: Dict[str, Any]) -> Optional[str]:
        """Extract reference from event data based on provider."""
        if provider == PaymentProvider.PAYSTACK:
            return event_data.get("reference")
        elif provider == PaymentProvider.FLUTTERWAVE:
            return event_data.get("tx_ref") or event_data.get("reference")
        return None


# Singleton instance
webhook_processor = WebhookProcessor()
