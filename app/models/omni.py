from __future__ import annotations

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from enum import Enum

from sqlalchemy import String, Integer, Boolean, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.agent import Agent, Team
    from app.models.unified_contact import UnifiedContact


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


class ConversationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ConversationStatus(str, Enum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    SNOOZED = "snoozed"
    CLOSED = "closed"


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
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("erpnext_leads.id"), nullable=True, index=True)

    # Link to unified contact (replaces customer_id/lead_id after migration)
    unified_contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("unified_contacts.id"),
        nullable=True,
        index=True
    )

    # Status & Priority
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True, default="open")
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="medium")

    # Assignment
    assigned_agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    assigned_team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Tracking
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False)
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # ["billing", "urgent"]

    # Contact info (denormalized for quick access)
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    contact_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Dates
    last_message_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    first_response_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    snoozed_until: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages: Mapped[List["OmniMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    assigned_agent: Mapped[Optional["Agent"]] = relationship(foreign_keys=[assigned_agent_id])
    assigned_team: Mapped[Optional["Team"]] = relationship(foreign_keys=[assigned_team_id])
    unified_contact: Mapped[Optional["UnifiedContact"]] = relationship(foreign_keys=[unified_contact_id])

    def __repr__(self) -> str:
        return f"<OmniConversation {self.id} channel={self.channel_id} status={self.status}>"


class OmniParticipant(Base):
    """Contact identity across channels."""

    __tablename__ = "omni_participants"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    handle: Mapped[str] = mapped_column(String(255), index=True)  # email/phone/social handle
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)

    # Link to unified contact (replaces customer_id after migration)
    unified_contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("unified_contacts.id"),
        nullable=True,
        index=True
    )

    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    unified_contact: Mapped[Optional["UnifiedContact"]] = relationship(foreign_keys=[unified_contact_id])

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


class InboxRoutingRule(Base):
    """Auto-routing rules for inbox conversations."""

    __tablename__ = "inbox_routing_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Conditions (JSON array of condition objects)
    # e.g., [{"type": "channel", "value": "email"}, {"type": "keyword", "value": "billing,invoice"}]
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)

    # Action configuration
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # assign_agent, assign_team, add_tag, create_ticket
    action_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # agent_id, team_id, tag name, etc.
    action_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Additional config

    # Ordering and state
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)  # Higher = checked first
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    match_count: Mapped[int] = mapped_column(Integer, default=0)  # How many times this rule matched

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<InboxRoutingRule {self.id} {self.name} active={self.is_active}>"


class InboxContact(Base):
    """
    Unified contact directory for inbox - links participants across channels.

    DEPRECATED: This model will be replaced by UnifiedContact.
    Use unified_contact_id to link to the new UnifiedContact model.
    """

    __tablename__ = "inbox_contacts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Primary identifiers
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Company info
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Links to other systems (legacy)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("erpnext_leads.id"), nullable=True, index=True)

    # Link to unified contact (migration target)
    unified_contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("unified_contacts.id"),
        nullable=True,
        index=True
    )

    # Contact metadata
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # ["vip", "enterprise"]
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Additional data

    # Stats (denormalized)
    total_conversations: Mapped[int] = mapped_column(Integer, default=0)
    last_contact_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    unified_contact: Mapped[Optional["UnifiedContact"]] = relationship(foreign_keys=[unified_contact_id])

    def __repr__(self) -> str:
        return f"<InboxContact {self.id} {self.name}>"
