from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Integer, Boolean, ForeignKey, JSON, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OmniChannelType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    CHATWOOT = "chatwoot"
    WEB = "web"
    CUSTOM = "custom"


class OmniChannel(Base):
    """External channel/account configuration."""

    __tablename__ = "omni_channels"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    webhook_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<OmniChannel {self.name} ({self.type})>"


class OmniConversation(Base):
    """Omnichannel conversation/thread."""

    __tablename__ = "omni_conversations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("omni_channels.id"), nullable=False, index=True)
    channel: Mapped[OmniChannel] = relationship()

    external_thread_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id"), nullable=True, index=True)

    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    messages: Mapped[List["OmniMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<OmniConversation {self.id} channel={self.channel_id} ticket={self.ticket_id}>"


class OmniParticipant(Base):
    """Contact identity across channels."""

    __tablename__ = "omni_participants"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    handle: Mapped[str] = mapped_column(String(255), index=True)  # email/phone/social handle
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<OmniParticipant {self.handle} ({self.channel_type})>"


class OmniMessage(Base):
    """Unified message record across channels."""

    __tablename__ = "omni_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("omni_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation: Mapped[OmniConversation] = relationship(back_populates="messages")

    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id"), nullable=True, index=True)
    participant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("omni_participants.id"), nullable=True, index=True)

    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    channel_id: Mapped[Optional[int]] = mapped_column(ForeignKey("omni_channels.id"), nullable=True, index=True)

    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # inbound|outbound
    message_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    body: Mapped[Optional[Text]] = mapped_column(Text, nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    delivery_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    attachments: Mapped[List["OmniAttachment"]] = relationship(back_populates="message", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<OmniMessage {self.id} dir={self.direction} conv={self.conversation_id}>"


class OmniAttachment(Base):
    """Attachment metadata linked to messages."""

    __tablename__ = "omni_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("omni_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    message: Mapped[OmniMessage] = relationship(back_populates="attachments")

    filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<OmniAttachment {self.filename or self.id}>"


class OmniWebhookEvent(Base):
    """Raw webhook events for audit/idempotency."""

    __tablename__ = "omni_webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    channel_id: Mapped[Optional[int]] = mapped_column(ForeignKey("omni_channels.id"), nullable=True, index=True)
    provider_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<OmniWebhookEvent {self.id} provider={self.provider_event_id}>"
