from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class LeadStatus(enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"
    ACTIVE = "active"  # converted to customer


class Lead(Base):
    """CRM leads/prospects from Splynx."""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)

    # Splynx ID
    splynx_id = Column(Integer, unique=True, index=True, nullable=False)

    # Basic info
    name = Column(String(255), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    billing_email = Column(String(255), nullable=True)
    phone = Column(String(100), nullable=True, index=True)
    login = Column(String(100), nullable=True)
    category = Column(String(50), nullable=True)  # private, business

    # Location info
    street_1 = Column(String(255), nullable=True)
    street_2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True, index=True)
    zip_code = Column(String(20), nullable=True)
    gps = Column(String(100), nullable=True)
    location_id = Column(Integer, nullable=True, index=True)

    # Assignment
    partner_id = Column(Integer, nullable=True, index=True)
    added_by = Column(String(100), nullable=True)
    added_by_id = Column(Integer, nullable=True)

    # Status tracking
    status = Column(String(50), nullable=True, index=True)  # new, active, etc.
    condition = Column(String(50), nullable=True)  # lead condition
    billing_type = Column(String(50), nullable=True)

    # Conversion tracking
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    conversion_date = Column(DateTime, nullable=True)

    # Dates
    date_add = Column(DateTime, nullable=True, index=True)
    last_online = Column(DateTime, nullable=True)
    last_update = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)

    # Relationships
    customer = relationship("Customer", backref="lead_records")

    def __repr__(self):
        return f"<Lead {self.name} ({self.status})>"
