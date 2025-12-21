from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base


class Administrator(Base):
    """Splynx administrators/staff members."""

    __tablename__ = "administrators"

    id = Column(Integer, primary_key=True, index=True)

    # Splynx ID
    splynx_id = Column(Integer, unique=True, index=True, nullable=False)

    # Basic info
    login = Column(String(100), nullable=True, index=True)
    name = Column(String(255), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(100), nullable=True)

    # Role and access
    role_name = Column(String(100), nullable=True)  # super-administrator, etc.
    router_access = Column(String(50), nullable=True)  # full, none, etc.
    partner_id = Column(Integer, nullable=True)

    # Activity tracking
    last_ip = Column(String(50), nullable=True)
    last_activity = Column(DateTime, nullable=True)

    # Settings
    calendar_color = Column(String(20), nullable=True)
    send_from_my_name = Column(String(10), nullable=True)

    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Administrator {self.name} ({self.role_name})>"
