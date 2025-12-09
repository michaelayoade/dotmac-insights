from __future__ import annotations

from sqlalchemy import String, Text, Enum, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
import enum
from app.database import Base


class MonitorState(enum.Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class NetworkMonitor(Base):
    """Network monitoring devices from Splynx."""

    __tablename__ = "network_monitors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Splynx ID
    splynx_id: Mapped[int] = mapped_column(unique=True, index=True, nullable=False)

    # Basic info
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    producer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Network info
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    snmp_port: Mapped[Optional[int]] = mapped_column(nullable=True)
    snmp_community: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    snmp_version: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Type and grouping
    device_type: Mapped[Optional[int]] = mapped_column(nullable=True)
    monitoring_group: Mapped[Optional[int]] = mapped_column(nullable=True)
    location_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    network_site_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Location
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gps: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    active: Mapped[bool] = mapped_column(default=True)
    send_notifications: Mapped[bool] = mapped_column(default=True)
    access_device: Mapped[bool] = mapped_column(default=False)

    # Ping monitoring
    is_ping: Mapped[bool] = mapped_column(default=True)
    ping_state: Mapped[MonitorState] = mapped_column(Enum(MonitorState), default=MonitorState.UNKNOWN)
    ping_time: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # SNMP monitoring
    snmp_state: Mapped[MonitorState] = mapped_column(Enum(MonitorState), default=MonitorState.UNKNOWN)
    snmp_time: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    snmp_uptime: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    snmp_status: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Timing
    delay_timer: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Dates
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<NetworkMonitor {self.title} ({self.ip_address})>"
