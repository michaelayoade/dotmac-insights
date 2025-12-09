from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class TicketMessage(Base):
    """Ticket messages/replies from Splynx support tickets."""

    __tablename__ = "ticket_messages"

    id = Column(Integer, primary_key=True, index=True)

    # Splynx ID
    splynx_id = Column(Integer, unique=True, index=True, nullable=False)

    # Relationships
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)
    splynx_ticket_id = Column(Integer, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    splynx_customer_id = Column(Integer, nullable=True, index=True)
    admin_id = Column(Integer, ForeignKey("administrators.id"), nullable=True, index=True)
    splynx_admin_id = Column(Integer, nullable=True, index=True)

    # Message content
    message = Column(Text, nullable=True)
    message_type = Column(String(50), nullable=True)  # admin, customer, system

    # Author info (denormalized for quick access)
    author_name = Column(String(255), nullable=True)
    author_email = Column(String(255), nullable=True)
    author_type = Column(String(50), nullable=True)  # admin, customer

    # Attachments info
    has_attachments = Column(Boolean, default=False)
    attachments_count = Column(Integer, default=0)

    # Message metadata
    is_internal = Column(Boolean, default=False)  # Internal staff notes
    is_read = Column(Boolean, default=False)

    # Dates
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)

    # Relationships
    ticket = relationship("Ticket", backref="messages")
    customer = relationship("Customer", backref="ticket_messages")
    admin = relationship("Administrator", backref="ticket_messages")

    def __repr__(self):
        return f"<TicketMessage {self.splynx_id} on Ticket {self.splynx_ticket_id}>"
