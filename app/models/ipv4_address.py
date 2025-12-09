from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class IPStatus(enum.Enum):
    AVAILABLE = "available"
    USED = "used"
    RESERVED = "reserved"


class IPv4Address(Base):
    """IPv4 address assignments from Splynx."""

    __tablename__ = "ipv4_addresses"

    id = Column(Integer, primary_key=True, index=True)

    # Splynx ID
    splynx_id = Column(Integer, unique=True, index=True, nullable=False)

    # IP details
    ip = Column(String(50), nullable=False, index=True)
    hostname = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    comment = Column(String(500), nullable=True)

    # Network info
    ipv4_network_id = Column(Integer, nullable=True, index=True)

    # Categorization
    host_category = Column(String(100), nullable=True)
    module = Column(String(100), nullable=True)  # customer, router, etc.
    module_item_id = Column(Integer, nullable=True)

    # Assignment
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    card_id = Column(Integer, nullable=True)  # network card/interface ID
    location_id = Column(Integer, nullable=True, index=True)

    # Status
    is_used = Column(Boolean, default=False)
    status = Column(String(50), nullable=True, index=True)

    # Last activity
    last_check = Column(DateTime, nullable=True)

    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)

    # Relationships
    customer = relationship("Customer", backref="ip_addresses")

    def __repr__(self):
        return f"<IPv4Address {self.ip} ({self.hostname or 'no hostname'})>"
