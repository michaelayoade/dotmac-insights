from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class ConversationStatus(enum.Enum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    SNOOZED = "snoozed"


class ConversationPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Conversation(Base):
    """Support conversations/tickets from Chatwoot."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)

    # External ID
    chatwoot_id = Column(Integer, unique=True, index=True, nullable=True)

    # Customer link
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    chatwoot_contact_id = Column(Integer, index=True, nullable=True)

    # Conversation details
    subject = Column(String(500), nullable=True)
    inbox_name = Column(String(255), nullable=True)  # Which inbox/channel
    channel = Column(String(100), nullable=True)  # email, whatsapp, web, etc.

    # Status & Priority
    status = Column(Enum(ConversationStatus), default=ConversationStatus.OPEN, index=True)
    priority = Column(Enum(ConversationPriority), default=ConversationPriority.MEDIUM)

    # Assignment
    assigned_agent_id = Column(Integer, nullable=True)
    assigned_agent_name = Column(String(255), nullable=True)
    assigned_team_id = Column(Integer, nullable=True)
    assigned_team_name = Column(String(255), nullable=True)

    # Categorization
    labels = Column(Text, nullable=True)  # JSON array of labels
    category = Column(String(100), nullable=True)  # Derived category: billing, technical, general

    # Counts
    message_count = Column(Integer, default=0)

    # Dates
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    first_response_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    last_activity_at = Column(DateTime, nullable=True)

    # Metrics
    first_response_time_seconds = Column(Integer, nullable=True)  # Time to first response
    resolution_time_seconds = Column(Integer, nullable=True)  # Total time to resolve

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")

    def __repr__(self):
        return f"<Conversation {self.chatwoot_id} - {self.status.value}>"

    @property
    def first_response_time_hours(self) -> float:
        if self.first_response_time_seconds:
            return self.first_response_time_seconds / 3600
        return 0

    @property
    def resolution_time_hours(self) -> float:
        if self.resolution_time_seconds:
            return self.resolution_time_seconds / 3600
        return 0


class Message(Base):
    """Individual messages within conversations."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)

    # External ID
    chatwoot_id = Column(Integer, unique=True, index=True, nullable=True)

    # Conversation link
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)

    # Message details
    content = Column(Text, nullable=True)
    message_type = Column(String(50), nullable=True)  # incoming, outgoing, activity
    is_private = Column(Boolean, default=False)  # Internal notes

    # Sender info
    sender_type = Column(String(50), nullable=True)  # contact, user, agent_bot
    sender_id = Column(Integer, nullable=True)
    sender_name = Column(String(255), nullable=True)

    # Dates
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.chatwoot_id} - {self.message_type}>"
