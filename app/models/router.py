from __future__ import annotations

from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from app.database import Base

if TYPE_CHECKING:
    from app.models.pop import Pop


class Router(Base):
    """Network routers/NAS from Splynx."""

    __tablename__ = "routers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External ID
    splynx_id: Mapped[int] = mapped_column(unique=True, index=True, nullable=False)

    # Basic info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Location
    location_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    pop_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pops.id"), nullable=True, index=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    gps: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Network
    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, index=True)
    nas_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, index=True)
    nas_type: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)

    # RADIUS Configuration (NAS)
    radius_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    radius_coa_port: Mapped[Optional[int]] = mapped_column(nullable=True)
    radius_accounting_interval: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Auth methods
    authorization_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    accounting_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # API/SSH access (for MikroTik, etc.)
    api_login: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    api_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    api_port: Mapped[Optional[int]] = mapped_column(nullable=True)
    ssh_port: Mapped[Optional[int]] = mapped_column(nullable=True)

    # IP Pools linked to this router
    pool_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of pool IDs

    # Partner/Reseller
    partners_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array

    # Additional RADIUS attributes
    additional_attributes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # Status
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    pop: Mapped[Optional[Pop]] = relationship(backref="routers")

    def __repr__(self) -> str:
        return f"<Router {self.title} ({self.ip}) NAS:{self.nas_type}>"
