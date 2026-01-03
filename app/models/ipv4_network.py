from __future__ import annotations

from sqlalchemy import String, Text, case, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
from typing import Optional
from app.database import Base


class IPv4Network(Base):
    """IPv4 Network subnets from Splynx."""

    __tablename__ = "ipv4_networks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Splynx ID
    splynx_id: Mapped[int] = mapped_column(unique=True, index=True, nullable=False)

    # Network info
    network: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    mask: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Type and usage
    network_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # rootnet, endnet
    type_of_usage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # pool, static, management
    network_category: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Hierarchy
    parent_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    rootnet: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Location
    location_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)

    # Usage stats
    used: Mapped[Optional[int]] = mapped_column(nullable=True)  # Count of used IPs
    allow_use_network_and_broadcast: Mapped[bool] = mapped_column(default=False)

    # Dates
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<IPv4Network {self.network}/{self.mask} - {self.title}>"

    @property
    def cidr(self) -> str:
        """Return network in CIDR notation."""
        return f"{self.network}/{self.mask}"

    @hybrid_property
    def total(self) -> int:
        """Total usable addresses in the subnet (accounts for network/broadcast)."""
        total = 1 << max(0, 32 - self.mask)
        if not self.allow_use_network_and_broadcast and total >= 2:
            return total - 2
        return total

    @total.expression
    def total(cls) -> object:
        base_total = func.power(2, 32 - cls.mask)
        return case(
            (cls.allow_use_network_and_broadcast.is_(True), base_total),
            else_=base_total - 2,
        )
