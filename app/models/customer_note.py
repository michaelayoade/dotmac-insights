from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class CustomerNote(Base):
    """Customer notes from Splynx."""

    __tablename__ = "customer_notes"

    id = Column(Integer, primary_key=True, index=True)

    # Splynx ID
    splynx_id = Column(Integer, unique=True, index=True, nullable=False)

    # Customer link
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    splynx_customer_id = Column(Integer, index=True, nullable=True)

    # Administrator who created the note
    administrator_id = Column(Integer, index=True, nullable=True)

    # Note content
    note_type = Column(String(50), nullable=True)  # comment, call, etc.
    note_class = Column(String(50), nullable=True)  # default, warning, etc.
    title = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)

    # Task-related fields
    assigned_to = Column(Integer, nullable=True)
    is_done = Column(Boolean, default=False)
    is_sent = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)
    pinned_date = Column(DateTime, nullable=True)
    scheduled_send_time = Column(DateTime, nullable=True)

    # Dates
    note_datetime = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)

    # Relationships
    customer = relationship("Customer", backref="customer_notes")

    def __repr__(self):
        return f"<CustomerNote {self.splynx_id} - {self.note_type}>"
