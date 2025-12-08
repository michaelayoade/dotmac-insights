from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Pop(Base):
    """Point of Presence - Network locations/sites."""

    __tablename__ = "pops"

    id = Column(Integer, primary_key=True, index=True)

    # External IDs
    splynx_id = Column(Integer, unique=True, index=True, nullable=True)

    # Basic info
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)  # Short code like "LKI" for Lekki

    # Location
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customers = relationship("Customer", back_populates="pop")

    def __repr__(self):
        return f"<Pop {self.name}>"
