"""Channel service - business logic for omnichannel management.

This service encapsulates channel-related business logic:
- Channel CRUD (email, WhatsApp, SMS, etc.)
- Connection testing
- Message delivery

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.omni import OmniChannel, OmniMessage
from app.services.validation.soft_validation_service import SoftValidationService

from .types import (
    ChannelCreate,
    ChannelUpdate,
    ConnectionTestResult,
    DeliveryResult,
)
from .errors import (
    ChannelConfigError,
    ChannelInactiveError,
    ChannelNotFoundError,
    MessageDeliveryError,
    ValidationError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["ChannelService"]


class ChannelService:
    """Service for channel management and message delivery.

    All methods that mutate data do NOT commit. The caller (route handler)
    is responsible for calling db.commit() after the operation succeeds.

    Args:
        db: SQLAlchemy database session.
        principal: Authenticated user/service token (for audit fields).
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        self.db = db
        self.principal = principal

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def list(
        self,
        active_only: bool = True,
        channel_type: Optional[str] = None,
    ) -> List[OmniChannel]:
        """List channels.

        Args:
            active_only: Only return active channels.
            channel_type: Filter by channel type.

        Returns:
            List of OmniChannel instances.
        """
        query = self.db.query(OmniChannel)

        if active_only:
            query = query.filter(OmniChannel.is_active == True)

        if channel_type:
            query = query.filter(OmniChannel.type == channel_type)

        return query.order_by(OmniChannel.name).all()

    def get(self, channel_id: int) -> OmniChannel:
        """Get a channel by ID.

        Args:
            channel_id: The channel ID.

        Returns:
            OmniChannel instance.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        channel = (
            self.db.query(OmniChannel)
            .filter(OmniChannel.id == channel_id)
            .first()
        )
        if not channel:
            raise ChannelNotFoundError(channel_id)
        return channel

    def get_by_name(self, name: str) -> OmniChannel:
        """Get a channel by name.

        Args:
            name: The channel name.

        Returns:
            OmniChannel instance.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        channel = (
            self.db.query(OmniChannel)
            .filter(OmniChannel.name == name)
            .first()
        )
        if not channel:
            raise ChannelNotFoundError(channel_name=name)
        return channel

    def get_by_chatwoot_inbox(self, chatwoot_inbox_id: int) -> Optional[OmniChannel]:
        """Get a channel by Chatwoot inbox ID.

        Args:
            chatwoot_inbox_id: The Chatwoot inbox ID.

        Returns:
            OmniChannel instance or None.
        """
        return (
            self.db.query(OmniChannel)
            .filter(OmniChannel.chatwoot_inbox_id == chatwoot_inbox_id)
            .first()
        )

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------

    def create(self, data: ChannelCreate) -> OmniChannel:
        """Create a new channel.

        Args:
            data: Channel creation data.

        Returns:
            Created OmniChannel instance.

        Raises:
            ValidationError: If channel name already exists.
            ChannelConfigError: If configuration is invalid.
        """
        # Check for duplicate name
        existing = (
            self.db.query(OmniChannel)
            .filter(OmniChannel.name == data.name)
            .first()
        )
        if existing:
            raise ValidationError(f"Channel with name '{data.name}' already exists")

        # Validate configuration based on type
        self._validate_config(data.type, data.config)

        channel = OmniChannel(
            name=data.name,
            type=data.type,
            config=data.config if data.config else None,
            webhook_secret=data.webhook_secret,
            is_active=data.is_active,
            chatwoot_inbox_id=data.chatwoot_inbox_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(channel)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(channel)
        return channel

    def update(
        self,
        channel_id: int,
        data: ChannelUpdate,
    ) -> OmniChannel:
        """Update a channel.

        Args:
            channel_id: The channel ID.
            data: Update data.

        Returns:
            Updated OmniChannel instance.

        Raises:
            ChannelNotFoundError: If channel not found.
            ValidationError: If new name conflicts.
            ChannelConfigError: If new configuration is invalid.
        """
        channel = self.get(channel_id)

        if data.name is not None and data.name != channel.name:
            # Check for duplicate name
            existing = (
                self.db.query(OmniChannel)
                .filter(OmniChannel.name == data.name, OmniChannel.id != channel_id)
                .first()
            )
            if existing:
                raise ValidationError(f"Channel with name '{data.name}' already exists")
            channel.name = data.name

        if data.config is not None:
            self._validate_config(channel.type, data.config)
            channel.config = data.config

        if data.webhook_secret is not None:
            channel.webhook_secret = data.webhook_secret

        if data.is_active is not None:
            channel.is_active = data.is_active

        if data.chatwoot_inbox_id is not None:
            channel.chatwoot_inbox_id = data.chatwoot_inbox_id

        channel.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(channel)
        return channel

    def delete(self, channel_id: int) -> bool:
        """Delete a channel.

        Args:
            channel_id: The channel ID.

        Returns:
            True if deleted.

        Raises:
            ChannelNotFoundError: If channel not found.
            ValidationError: If channel has active conversations.
        """
        channel = self.get(channel_id)

        # Check for active conversations
        from app.models.omni import OmniConversation

        active_count = (
            self.db.query(func.count(OmniConversation.id))
            .filter(
                OmniConversation.channel_id == channel_id,
                OmniConversation.status.in_(["open", "pending"]),
            )
            .scalar()
        )
        if active_count > 0:
            raise ValidationError(
                f"Cannot delete channel with {active_count} active conversations"
            )

        self.db.delete(channel)
        self.db.flush()
        return True

    def activate(self, channel_id: int) -> OmniChannel:
        """Activate a channel.

        Args:
            channel_id: The channel ID.

        Returns:
            Updated OmniChannel instance.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        channel = self.get(channel_id)
        channel.is_active = True
        channel.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(channel)
        return channel

    def deactivate(self, channel_id: int) -> OmniChannel:
        """Deactivate a channel.

        Args:
            channel_id: The channel ID.

        Returns:
            Updated OmniChannel instance.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        channel = self.get(channel_id)
        channel.is_active = False
        channel.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(channel)
        return channel

    # -------------------------------------------------------------------------
    # Configuration Validation
    # -------------------------------------------------------------------------

    def _validate_config(self, channel_type: str, config: dict) -> None:
        """Validate channel configuration based on type.

        Args:
            channel_type: The channel type.
            config: The configuration dict.

        Raises:
            ChannelConfigError: If configuration is invalid.
        """
        if not config:
            return  # Allow empty config

        validators = {
            "email": self._validate_email_config,
            "whatsapp": self._validate_whatsapp_config,
            "sms": self._validate_sms_config,
            "chatwoot": self._validate_chatwoot_config,
        }

        validator = validators.get(channel_type)
        if validator:
            validator(config)

    def _validate_email_config(self, config: dict) -> None:
        """Validate email channel configuration."""
        # Optional fields: smtp_host, smtp_port, imap_host, imap_port, etc.
        pass

    def _validate_whatsapp_config(self, config: dict) -> None:
        """Validate WhatsApp channel configuration."""
        # Optional fields: business_phone_id, access_token, api_version
        pass

    def _validate_sms_config(self, config: dict) -> None:
        """Validate SMS channel configuration."""
        # Optional fields: provider, api_key, from_number
        pass

    def _validate_chatwoot_config(self, config: dict) -> None:
        """Validate Chatwoot channel configuration."""
        # Optional fields: api_key, account_id, base_url
        pass

    # -------------------------------------------------------------------------
    # Connection Testing
    # -------------------------------------------------------------------------

    def test_connection(self, channel_id: int) -> ConnectionTestResult:
        """Test channel connection.

        Args:
            channel_id: The channel ID.

        Returns:
            ConnectionTestResult with success status and details.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        channel = self.get(channel_id)

        testers = {
            "email": self._test_email_connection,
            "whatsapp": self._test_whatsapp_connection,
            "sms": self._test_sms_connection,
            "chatwoot": self._test_chatwoot_connection,
        }

        tester = testers.get(channel.type)
        if not tester:
            return ConnectionTestResult(
                success=True,
                message=f"No connection test available for {channel.type} channels",
            )

        return tester(channel)

    def _test_email_connection(self, channel: OmniChannel) -> ConnectionTestResult:
        """Test email channel connection."""
        # TODO: Implement actual email connection test
        return ConnectionTestResult(
            success=True,
            message="Email connection test not yet implemented",
        )

    def _test_whatsapp_connection(self, channel: OmniChannel) -> ConnectionTestResult:
        """Test WhatsApp channel connection."""
        # TODO: Implement actual WhatsApp API test
        return ConnectionTestResult(
            success=True,
            message="WhatsApp connection test not yet implemented",
        )

    def _test_sms_connection(self, channel: OmniChannel) -> ConnectionTestResult:
        """Test SMS channel connection."""
        # TODO: Implement actual SMS provider test
        return ConnectionTestResult(
            success=True,
            message="SMS connection test not yet implemented",
        )

    def _test_chatwoot_connection(self, channel: OmniChannel) -> ConnectionTestResult:
        """Test Chatwoot channel connection."""
        # TODO: Implement actual Chatwoot API test
        return ConnectionTestResult(
            success=True,
            message="Chatwoot connection test not yet implemented",
        )

    # -------------------------------------------------------------------------
    # Message Delivery
    # -------------------------------------------------------------------------

    def send_message(
        self,
        channel_id: int,
        message: OmniMessage,
    ) -> DeliveryResult:
        """Send a message via a channel.

        Args:
            channel_id: The channel ID.
            message: The message to send.

        Returns:
            DeliveryResult with success status and provider info.

        Raises:
            ChannelNotFoundError: If channel not found.
            ChannelInactiveError: If channel is not active.
            MessageDeliveryError: If delivery fails.
        """
        channel = self.get(channel_id)

        if not channel.is_active:
            raise ChannelInactiveError(channel_id)

        senders = {
            "email": self._send_email,
            "whatsapp": self._send_whatsapp,
            "sms": self._send_sms,
            "chatwoot": self._send_chatwoot,
        }

        sender = senders.get(channel.type)
        if not sender:
            # For unknown channel types, just mark as sent
            return DeliveryResult(
                success=True,
                delivered_at=datetime.now(timezone.utc),
                meta={"note": f"No delivery implementation for {channel.type}"},
            )

        return sender(channel, message)

    def _send_email(
        self,
        channel: OmniChannel,
        message: OmniMessage,
    ) -> DeliveryResult:
        """Send message via email."""
        # TODO: Implement actual email sending
        return DeliveryResult(
            success=True,
            delivered_at=datetime.now(timezone.utc),
            meta={"note": "Email delivery not yet implemented"},
        )

    def _send_whatsapp(
        self,
        channel: OmniChannel,
        message: OmniMessage,
    ) -> DeliveryResult:
        """Send message via WhatsApp."""
        # TODO: Implement actual WhatsApp API call
        return DeliveryResult(
            success=True,
            delivered_at=datetime.now(timezone.utc),
            meta={"note": "WhatsApp delivery not yet implemented"},
        )

    def _send_sms(
        self,
        channel: OmniChannel,
        message: OmniMessage,
    ) -> DeliveryResult:
        """Send message via SMS."""
        # TODO: Implement actual SMS provider call
        return DeliveryResult(
            success=True,
            delivered_at=datetime.now(timezone.utc),
            meta={"note": "SMS delivery not yet implemented"},
        )

    def _send_chatwoot(
        self,
        channel: OmniChannel,
        message: OmniMessage,
    ) -> DeliveryResult:
        """Send message via Chatwoot."""
        # TODO: Implement actual Chatwoot API call
        return DeliveryResult(
            success=True,
            delivered_at=datetime.now(timezone.utc),
            meta={"note": "Chatwoot delivery not yet implemented"},
        )
