"""Webhook service - business logic for inbound webhook processing.

This service encapsulates webhook-related business logic:
- Signature validation
- Idempotency checking
- Event recording
- Routing to appropriate handlers

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.models.omni import OmniChannel, OmniWebhookEvent

from .types import WebhookEventData, WebhookResult
from .errors import (
    ChannelNotFoundError,
    DuplicateWebhookError,
    WebhookProcessingError,
    WebhookValidationError,
)

if TYPE_CHECKING:
    from app.auth import Principal
    from .channels import ChannelService
    from .conversations import ConversationService
    from .messages import MessageService

__all__ = ["WebhookService"]


class WebhookService:
    """Service for webhook processing.

    This service handles inbound webhooks from various channels:
    1. Validates webhook signatures
    2. Checks for duplicate events (idempotency)
    3. Records events for audit
    4. Routes to appropriate handlers

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token.
        conversation_service: Optional ConversationService instance.
        message_service: Optional MessageService instance.
        channel_service: Optional ChannelService instance.
    """

    def __init__(
        self,
        db: Session,
        principal: Optional["Principal"] = None,
        conversation_service: Optional["ConversationService"] = None,
        message_service: Optional["MessageService"] = None,
        channel_service: Optional["ChannelService"] = None,
    ) -> None:
        self.db = db
        self.principal = principal
        self._conversation_service = conversation_service
        self._message_service = message_service
        self._channel_service = channel_service

    @property
    def conversation_service(self) -> "ConversationService":
        if self._conversation_service is None:
            from .conversations import ConversationService

            self._conversation_service = ConversationService(self.db, self.principal)
        return self._conversation_service

    @property
    def message_service(self) -> "MessageService":
        if self._message_service is None:
            from .messages import MessageService

            self._message_service = MessageService(self.db, self.principal)
        return self._message_service

    @property
    def channel_service(self) -> "ChannelService":
        if self._channel_service is None:
            from .channels import ChannelService

            self._channel_service = ChannelService(self.db, self.principal)
        return self._channel_service

    # -------------------------------------------------------------------------
    # Main Entry Point
    # -------------------------------------------------------------------------

    def ingest(
        self,
        channel_id: int,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        raw_body: Optional[bytes] = None,
    ) -> WebhookResult:
        """Ingest a webhook event.

        This is the main entry point for processing webhooks.

        Args:
            channel_id: The channel ID.
            payload: Parsed JSON payload.
            headers: HTTP headers.
            raw_body: Raw request body for signature validation.

        Returns:
            WebhookResult with processing outcome.

        Raises:
            ChannelNotFoundError: If channel not found.
            WebhookValidationError: If signature validation fails.
            DuplicateWebhookError: If event was already processed.
        """
        # Get channel
        channel = self.channel_service.get(channel_id)

        # Extract provider event ID for idempotency
        provider_event_id = self._extract_event_id(channel.type, payload, headers)

        # Check for duplicate
        if provider_event_id and self.is_duplicate(channel_id, provider_event_id):
            return WebhookResult(
                success=True,
                is_duplicate=True,
                action_taken="skipped_duplicate",
            )

        # Validate signature if webhook_secret is set and raw_body provided
        if channel.webhook_secret and raw_body:
            signature = self._extract_signature(channel.type, headers)
            if signature and not self.validate_signature(
                channel, raw_body, signature
            ):
                raise WebhookValidationError(
                    "Invalid webhook signature",
                    reason="signature_mismatch",
                )

        # Record event
        event = self._record_event(
            channel_id=channel_id,
            provider_event_id=provider_event_id,
            payload=payload,
            headers=headers,
        )

        # Process based on channel type
        try:
            result = self._process_event(channel, payload, headers)
            event.processed = True
            self.db.flush()
            return WebhookResult(
                success=True,
                event_id=event.id,
                conversation_id=result.get("conversation_id"),
                message_id=result.get("message_id"),
                action_taken=result.get("action"),
            )
        except Exception as e:
            event.error = str(e)
            self.db.flush()
            raise WebhookProcessingError(str(e), event_id=event.id)

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def validate_signature(
        self,
        channel: OmniChannel,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Validate webhook signature.

        Args:
            channel: The channel with webhook_secret.
            payload: Raw request body.
            signature: Signature from headers.

        Returns:
            True if valid, False otherwise.
        """
        if not channel.webhook_secret:
            return True  # No secret = no validation

        validators = {
            "whatsapp": self._validate_whatsapp_signature,
            "chatwoot": self._validate_chatwoot_signature,
            "email": self._validate_email_signature,
        }

        validator = validators.get(channel.type, self._validate_default_signature)
        return validator(channel.webhook_secret, payload, signature)

    def _validate_default_signature(
        self,
        secret: str,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Default HMAC-SHA256 signature validation."""
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        # Handle signatures with sha256= prefix
        if signature.startswith("sha256="):
            signature = signature[7:]

        return hmac.compare_digest(expected.lower(), signature.lower())

    def _validate_whatsapp_signature(
        self,
        secret: str,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Validate WhatsApp webhook signature."""
        return self._validate_default_signature(secret, payload, signature)

    def _validate_chatwoot_signature(
        self,
        secret: str,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Validate Chatwoot webhook signature."""
        return self._validate_default_signature(secret, payload, signature)

    def _validate_email_signature(
        self,
        secret: str,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Validate email webhook signature (provider-specific)."""
        return self._validate_default_signature(secret, payload, signature)

    # -------------------------------------------------------------------------
    # Idempotency
    # -------------------------------------------------------------------------

    def is_duplicate(
        self,
        channel_id: int,
        provider_event_id: str,
    ) -> bool:
        """Check if an event is a duplicate.

        Args:
            channel_id: The channel ID.
            provider_event_id: Provider's event ID.

        Returns:
            True if duplicate, False otherwise.
        """
        existing = (
            self.db.query(OmniWebhookEvent)
            .filter(
                OmniWebhookEvent.channel_id == channel_id,
                OmniWebhookEvent.provider_event_id == provider_event_id,
            )
            .first()
        )
        return existing is not None

    # -------------------------------------------------------------------------
    # Event Recording
    # -------------------------------------------------------------------------

    def _record_event(
        self,
        channel_id: int,
        provider_event_id: Optional[str],
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> OmniWebhookEvent:
        """Record a webhook event for audit."""
        event = OmniWebhookEvent(
            channel_id=channel_id,
            provider_event_id=provider_event_id,
            payload=payload,
            headers=headers,
            processed=False,
            received_at=datetime.now(timezone.utc),
        )
        self.db.add(event)
        self.db.flush()
        return event

    def get_event(self, event_id: int) -> Optional[OmniWebhookEvent]:
        """Get a webhook event by ID."""
        return (
            self.db.query(OmniWebhookEvent)
            .filter(OmniWebhookEvent.id == event_id)
            .first()
        )

    def list_events(
        self,
        channel_id: Optional[int] = None,
        processed: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[OmniWebhookEvent], int]:
        """List webhook events with filters."""
        query = self.db.query(OmniWebhookEvent)
        if channel_id:
            query = query.filter(OmniWebhookEvent.channel_id == channel_id)
        if processed is not None:
            query = query.filter(OmniWebhookEvent.processed == processed)

        total = query.count()
        events = (
            query.order_by(OmniWebhookEvent.received_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return events, total

    def retry_event(self, event_id: int) -> WebhookResult:
        """Retry processing a failed webhook event.

        Args:
            event_id: The event ID.

        Returns:
            WebhookResult with processing outcome.

        Raises:
            WebhookProcessingError: If event not found or retry fails.
        """
        event = self.get_event(event_id)
        if not event:
            raise WebhookProcessingError(f"Event not found: {event_id}")

        if event.processed:
            return WebhookResult(
                success=True,
                event_id=event_id,
                action_taken="already_processed",
            )

        channel = self.channel_service.get(event.channel_id)
        now = datetime.now(timezone.utc)
        event.retry_count = (event.retry_count or 0) + 1
        event.last_retry_at = now

        try:
            result = self._process_event(channel, event.payload, event.headers or {})
            event.processed = True
            event.error = None
            self.db.flush()
            return WebhookResult(
                success=True,
                event_id=event_id,
                conversation_id=result.get("conversation_id"),
                message_id=result.get("message_id"),
                action_taken=result.get("action"),
            )
        except Exception as e:
            event.error = str(e)
            self.db.flush()
            raise WebhookProcessingError(str(e), event_id=event_id)

    # -------------------------------------------------------------------------
    # Event Processing
    # -------------------------------------------------------------------------

    def _process_event(
        self,
        channel: OmniChannel,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """Process a webhook event based on channel type.

        Returns dict with: action, conversation_id, message_id
        """
        processors = {
            "whatsapp": self._process_whatsapp_event,
            "chatwoot": self._process_chatwoot_event,
            "email": self._process_email_event,
        }

        processor = processors.get(channel.type, self._process_generic_event)
        return processor(channel, payload, headers)

    def _process_whatsapp_event(
        self,
        channel: OmniChannel,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """Process WhatsApp webhook event."""
        # Extract message from WhatsApp payload structure
        # This is a simplified implementation
        result: Dict[str, Any] = {"action": "processed"}

        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            result["action"] = "no_messages"
            return result

        # Process first message
        msg_data = messages[0]
        from_number = msg_data.get("from", "")
        text = msg_data.get("text", {}).get("body", "")
        msg_id = msg_data.get("id", "")

        # TODO: Create conversation/message using services
        result["action"] = "message_received"
        return result

    def _process_chatwoot_event(
        self,
        channel: OmniChannel,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """Process Chatwoot webhook event."""
        result: Dict[str, Any] = {"action": "processed"}

        event_type = payload.get("event")

        if event_type == "message_created":
            # Handle new message
            result["action"] = "message_created"
        elif event_type == "conversation_status_changed":
            # Handle status change
            result["action"] = "status_changed"
        elif event_type == "conversation_created":
            # Handle new conversation
            result["action"] = "conversation_created"
        else:
            result["action"] = f"unknown_event_{event_type}"

        return result

    def _process_email_event(
        self,
        channel: OmniChannel,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """Process email webhook event (e.g., from email provider)."""
        result: Dict[str, Any] = {"action": "processed"}

        # Extract email data based on provider format
        # This would vary by email provider (SendGrid, Mailgun, etc.)

        result["action"] = "email_received"
        return result

    def _process_generic_event(
        self,
        channel: OmniChannel,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """Process generic webhook event."""
        return {"action": "generic_processed"}

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _extract_event_id(
        self,
        channel_type: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Optional[str]:
        """Extract provider event ID from payload/headers."""
        extractors = {
            "whatsapp": lambda p, h: p.get("entry", [{}])[0]
            .get("changes", [{}])[0]
            .get("value", {})
            .get("messages", [{}])[0]
            .get("id"),
            "chatwoot": lambda p, h: str(p.get("id", "")),
            "email": lambda p, h: h.get("X-Message-Id")
            or h.get("Message-Id")
            or p.get("message_id"),
        }

        extractor = extractors.get(channel_type)
        if extractor:
            try:
                event_id = extractor(payload, headers)
                return event_id if event_id else None
            except (KeyError, IndexError):
                return None
        return None

    def _extract_signature(
        self,
        channel_type: str,
        headers: Dict[str, str],
    ) -> Optional[str]:
        """Extract signature from headers based on channel type."""
        header_names = {
            "whatsapp": "X-Hub-Signature-256",
            "chatwoot": "X-Chatwoot-Signature",
            "email": "X-Signature",
        }

        header = header_names.get(channel_type, "X-Signature")

        # Try case-insensitive lookup
        for key, value in headers.items():
            if key.lower() == header.lower():
                return value

        return None
