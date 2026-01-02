"""Message service - business logic for omnichannel messages.

This service encapsulates message-related business logic:
- Creating inbound/outbound messages
- Delivery status tracking
- Read status management
- Conversation stat updates
- Attachments

Routes should call this service and control the transaction boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.omni import (
    OmniAttachment,
    OmniConversation,
    OmniMessage,
)
from app.services.types import PaginatedResult, PaginationParams

from .types import (
    AttachmentData,
    InboundMessageData,
    InternalNoteData,
    MessageFilters,
    OutboundMessageData,
)
from .errors import (
    ConversationNotFoundError,
    DuplicateMessageError,
    MessageNotFoundError,
)

if TYPE_CHECKING:
    from app.auth import Principal

__all__ = ["MessageService"]


class MessageService:
    """Service for message business logic.

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

    def list_for_conversation(
        self,
        conversation_id: int,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[OmniMessage]:
        """List messages for a conversation.

        Args:
            conversation_id: The conversation ID.
            before: Only messages before this time.
            after: Only messages after this time.
            limit: Maximum number of messages.

        Returns:
            List of OmniMessage instances.
        """
        query = (
            self.db.query(OmniMessage)
            .options(selectinload(OmniMessage.attachments))
            .filter(OmniMessage.conversation_id == conversation_id)
        )

        if before:
            query = query.filter(OmniMessage.created_at < before)

        if after:
            query = query.filter(OmniMessage.created_at > after)

        query = query.order_by(OmniMessage.created_at.desc()).limit(limit)

        messages = query.all()
        return list(reversed(messages))  # Return in chronological order

    def get(self, message_id: int) -> OmniMessage:
        """Get a message by ID.

        Args:
            message_id: The message ID.

        Returns:
            OmniMessage instance.

        Raises:
            MessageNotFoundError: If message not found.
        """
        msg = (
            self.db.query(OmniMessage)
            .options(selectinload(OmniMessage.attachments))
            .filter(OmniMessage.id == message_id)
            .first()
        )
        if not msg:
            raise MessageNotFoundError(message_id)
        return msg

    def get_by_provider_id(
        self,
        provider_message_id: str,
        channel_id: Optional[int] = None,
    ) -> Optional[OmniMessage]:
        """Get a message by provider message ID.

        Args:
            provider_message_id: The provider's message ID.
            channel_id: Optional channel ID to scope the search.

        Returns:
            OmniMessage instance or None if not found.
        """
        query = self.db.query(OmniMessage).filter(
            OmniMessage.provider_message_id == provider_message_id
        )
        if channel_id:
            query = query.filter(OmniMessage.channel_id == channel_id)
        return query.first()

    def exists_by_provider_id(
        self,
        provider_message_id: str,
        channel_id: Optional[int] = None,
    ) -> bool:
        """Check if a message exists by provider message ID.

        Args:
            provider_message_id: The provider's message ID.
            channel_id: Optional channel ID to scope the search.

        Returns:
            True if message exists, False otherwise.
        """
        return self.get_by_provider_id(provider_message_id, channel_id) is not None

    # -------------------------------------------------------------------------
    # Create Messages
    # -------------------------------------------------------------------------

    def _get_conversation(self, conversation_id: int) -> OmniConversation:
        """Get conversation or raise ConversationNotFoundError."""
        conv = self.db.query(OmniConversation).filter(
            OmniConversation.id == conversation_id
        ).first()
        if not conv:
            raise ConversationNotFoundError(conversation_id)
        return conv

    def _update_conversation_stats(
        self,
        conv: OmniConversation,
        is_inbound: bool,
        is_private: bool = False,
    ) -> None:
        """Update conversation stats after message creation."""
        now = datetime.now(timezone.utc)

        conv.message_count = (conv.message_count or 0) + 1
        conv.last_message_at = now
        conv.updated_at = now

        if is_inbound:
            conv.unread_count = (conv.unread_count or 0) + 1
        elif not is_private:
            # Track first response time (agent replies only)
            if not conv.first_response_at:
                conv.first_response_at = now

    def create_inbound(self, data: InboundMessageData) -> OmniMessage:
        """Create an inbound message (from customer).

        Args:
            data: Inbound message data.

        Returns:
            Created OmniMessage instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
            DuplicateMessageError: If provider_message_id already exists.
        """
        # Check for duplicates
        if data.provider_message_id:
            if self.exists_by_provider_id(data.provider_message_id, data.channel_id):
                raise DuplicateMessageError(data.provider_message_id)

        conv = self._get_conversation(data.conversation_id)

        msg = OmniMessage(
            conversation_id=conv.id,
            direction="inbound",
            body=data.body,
            subject=data.subject,
            message_type=data.message_type or "incoming",
            participant_id=data.participant_id,
            channel_id=data.channel_id or conv.channel_id,
            provider_message_id=data.provider_message_id,
            meta=data.meta if data.meta else None,
            sent_at=data.sent_at or datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(msg)
        self.db.flush()

        # Add attachments
        for att_data in data.attachments:
            self._add_attachment(msg, att_data)

        # Update conversation stats
        self._update_conversation_stats(conv, is_inbound=True)
        self.db.flush()

        return msg

    def create_outbound(self, data: OutboundMessageData) -> OmniMessage:
        """Create an outbound message (from agent).

        Args:
            data: Outbound message data.

        Returns:
            Created OmniMessage instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        conv = self._get_conversation(data.conversation_id)

        msg = OmniMessage(
            conversation_id=conv.id,
            direction="outbound",
            body=data.body,
            subject=data.subject,
            message_type=data.message_type or "outgoing",
            agent_id=data.agent_id,
            channel_id=data.channel_id or conv.channel_id,
            meta=data.meta if data.meta else None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(msg)
        self.db.flush()

        # Add attachments
        for att_data in data.attachments:
            self._add_attachment(msg, att_data)

        # Update conversation stats
        self._update_conversation_stats(conv, is_inbound=False)
        self.db.flush()

        return msg

    def create_internal_note(self, data: InternalNoteData) -> OmniMessage:
        """Create an internal note (not visible to customer).

        Args:
            data: Internal note data.

        Returns:
            Created OmniMessage instance.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        conv = self._get_conversation(data.conversation_id)

        meta = {"mentioned_agent_ids": data.mentioned_agent_ids} if data.mentioned_agent_ids else None

        msg = OmniMessage(
            conversation_id=conv.id,
            direction="outbound",
            body=data.body,
            message_type="private_note",
            agent_id=data.agent_id,
            channel_id=conv.channel_id,
            meta=meta,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(msg)
        self.db.flush()

        # Update conversation stats (private notes don't trigger first response)
        self._update_conversation_stats(conv, is_inbound=False, is_private=True)
        self.db.flush()

        return msg

    # -------------------------------------------------------------------------
    # Delivery Tracking
    # -------------------------------------------------------------------------

    def mark_delivered(
        self,
        message_id: int,
        provider_message_id: Optional[str] = None,
    ) -> OmniMessage:
        """Mark a message as delivered.

        Args:
            message_id: The message ID.
            provider_message_id: Optional provider's message ID.

        Returns:
            Updated OmniMessage instance.

        Raises:
            MessageNotFoundError: If message not found.
        """
        msg = self.get(message_id)

        msg.delivery_status = "delivered"
        msg.delivered_at = datetime.now(timezone.utc)
        if provider_message_id:
            msg.provider_message_id = provider_message_id
        msg.updated_at = datetime.now(timezone.utc)

        self.db.flush()
        return msg

    def mark_sent(
        self,
        message_id: int,
        provider_message_id: Optional[str] = None,
    ) -> OmniMessage:
        """Mark a message as sent.

        Args:
            message_id: The message ID.
            provider_message_id: Optional provider's message ID.

        Returns:
            Updated OmniMessage instance.

        Raises:
            MessageNotFoundError: If message not found.
        """
        msg = self.get(message_id)

        msg.delivery_status = "sent"
        msg.sent_at = datetime.now(timezone.utc)
        if provider_message_id:
            msg.provider_message_id = provider_message_id
        msg.updated_at = datetime.now(timezone.utc)

        self.db.flush()
        return msg

    def mark_read(self, message_id: int) -> OmniMessage:
        """Mark a message as read.

        Args:
            message_id: The message ID.

        Returns:
            Updated OmniMessage instance.

        Raises:
            MessageNotFoundError: If message not found.
        """
        msg = self.get(message_id)

        msg.read_at = datetime.now(timezone.utc)
        msg.updated_at = datetime.now(timezone.utc)

        # Decrement conversation unread count
        if msg.direction == "inbound":
            conv = msg.conversation
            if conv and conv.unread_count > 0:
                conv.unread_count -= 1

        self.db.flush()
        return msg

    def mark_failed(
        self,
        message_id: int,
        error: str,
        error_code: Optional[str] = None,
    ) -> OmniMessage:
        """Mark a message as failed.

        Args:
            message_id: The message ID.
            error: Error message.
            error_code: Optional error code.

        Returns:
            Updated OmniMessage instance.

        Raises:
            MessageNotFoundError: If message not found.
        """
        msg = self.get(message_id)

        msg.delivery_status = "failed"
        msg.meta = msg.meta or {}
        msg.meta["delivery_error"] = error
        if error_code:
            msg.meta["delivery_error_code"] = error_code
        msg.updated_at = datetime.now(timezone.utc)

        self.db.flush()
        return msg

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def mark_conversation_read(self, conversation_id: int) -> int:
        """Mark all inbound messages in a conversation as read.

        Args:
            conversation_id: The conversation ID.

        Returns:
            Number of messages marked as read.

        Raises:
            ConversationNotFoundError: If conversation not found.
        """
        conv = self._get_conversation(conversation_id)

        now = datetime.now(timezone.utc)

        updated = (
            self.db.query(OmniMessage)
            .filter(
                OmniMessage.conversation_id == conversation_id,
                OmniMessage.direction == "inbound",
                OmniMessage.read_at.is_(None),
            )
            .update({"read_at": now, "updated_at": now})
        )

        conv.unread_count = 0
        conv.updated_at = now

        self.db.flush()
        return updated

    # -------------------------------------------------------------------------
    # Attachments
    # -------------------------------------------------------------------------

    def _add_attachment(self, msg: OmniMessage, data: AttachmentData) -> OmniAttachment:
        """Add an attachment to a message.

        Args:
            msg: The message to attach to.
            data: Attachment data.

        Returns:
            Created OmniAttachment instance.
        """
        attachment = OmniAttachment(
            message_id=msg.id,
            filename=data.filename,
            url=data.url,
            mime_type=data.mime_type,
            size_bytes=data.size_bytes,
            meta=data.meta if data.meta else None,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(attachment)
        self.db.flush()
        return attachment

    def add_attachment(
        self,
        message_id: int,
        data: AttachmentData,
    ) -> OmniAttachment:
        """Add an attachment to an existing message.

        Args:
            message_id: The message ID.
            data: Attachment data.

        Returns:
            Created OmniAttachment instance.

        Raises:
            MessageNotFoundError: If message not found.
        """
        msg = self.get(message_id)
        return self._add_attachment(msg, data)

    def get_attachments(self, message_id: int) -> List[OmniAttachment]:
        """Get all attachments for a message.

        Args:
            message_id: The message ID.

        Returns:
            List of OmniAttachment instances.
        """
        return (
            self.db.query(OmniAttachment)
            .filter(OmniAttachment.message_id == message_id)
            .all()
        )

    def delete_attachment(self, attachment_id: int) -> bool:
        """Delete an attachment.

        Args:
            attachment_id: The attachment ID.

        Returns:
            True if deleted, False if not found.
        """
        attachment = self.db.query(OmniAttachment).filter(
            OmniAttachment.id == attachment_id
        ).first()

        if not attachment:
            return False

        self.db.delete(attachment)
        self.db.flush()
        return True
