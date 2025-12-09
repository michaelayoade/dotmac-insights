from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.employee import Employee


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

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External ID
    chatwoot_id: Mapped[Optional[int]] = mapped_column(unique=True, index=True, nullable=True)

    # Customer link
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    chatwoot_contact_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)

    # Conversation details
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    inbox_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    channel: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status & Priority
    status: Mapped[ConversationStatus] = mapped_column(Enum(ConversationStatus), default=ConversationStatus.OPEN, index=True)
    priority: Mapped[ConversationPriority] = mapped_column(Enum(ConversationPriority), default=ConversationPriority.MEDIUM)

    # Assignment (Chatwoot agent info)
    assigned_agent_id: Mapped[Optional[int]] = mapped_column(nullable=True)  # Chatwoot agent ID
    assigned_agent_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    assigned_team_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    assigned_team_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Link to Employee (via chatwoot_agent_id match)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)

    # Categorization
    labels: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Counts
    message_count: Mapped[int] = mapped_column(default=0)

    # Dates
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    first_response_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Metrics
    first_response_time_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    resolution_time_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped[Optional[Customer]] = relationship(back_populates="conversations")
    messages: Mapped[List[Message]] = relationship(back_populates="conversation")
    employee: Mapped[Optional["Employee"]] = relationship(foreign_keys=[employee_id])

    def __repr__(self) -> str:
        return f"<Conversation {self.chatwoot_id} - {self.status.value}>"

    @property
    def first_response_time_hours(self) -> float:
        if self.first_response_time_seconds:
            return self.first_response_time_seconds / 3600
        return 0.0

    @property
    def resolution_time_hours(self) -> float:
        if self.resolution_time_seconds:
            return self.resolution_time_seconds / 3600
        return 0.0


class Message(Base):
    """Individual messages within conversations."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External ID
    chatwoot_id: Mapped[Optional[int]] = mapped_column(unique=True, index=True, nullable=True)

    # Conversation link
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)

    # Message details
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_private: Mapped[bool] = mapped_column(default=False)

    # Sender info
    sender_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sender_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    sender_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Dates
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Relationships
    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message {self.chatwoot_id} - {self.message_type}>"
