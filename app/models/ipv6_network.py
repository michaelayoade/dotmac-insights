from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
from app.database import Base


class IPv6Network(Base):
    """IPv6 Network subnets from Splynx."""

    __tablename__ = "ipv6_networks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Splynx ID
    splynx_id: Mapped[int] = mapped_column(unique=True, index=True, nullable=False)

    # Network details
    network: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    prefix: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Network classification
    network_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    type_of_usage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    network_category: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Hierarchy
    parent_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    rootnet: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Location
    location_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)

    # Usage tracking
    used: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Dates
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    @property
    def cidr(self) -> str:
        """Return CIDR notation for the network."""
        return f"{self.network}/{self.prefix}"

    def __repr__(self) -> str:
        return f"<IPv6Network {self.cidr}>"
