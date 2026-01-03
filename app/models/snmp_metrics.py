"""SNMP Metrics Models.

Models for storing device and interface metrics collected via SNMP polling.
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.router import Router
    from app.models.subscription import Subscription


# =============================================================================
# SNMP Polling Configuration
# =============================================================================


class SNMPVersion(str, enum.Enum):
    """SNMP protocol version."""

    V2C = "2c"
    V3 = "3"


class SNMPAuthProtocol(str, enum.Enum):
    """SNMPv3 authentication protocol."""

    MD5 = "md5"
    SHA = "sha"
    SHA224 = "sha224"
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"


class SNMPPrivProtocol(str, enum.Enum):
    """SNMPv3 privacy protocol."""

    DES = "des"
    AES = "aes"
    AES192 = "aes192"
    AES256 = "aes256"


class PollStatus(str, enum.Enum):
    """Status of last polling attempt."""

    SUCCESS = "success"
    TIMEOUT = "timeout"
    AUTH_ERROR = "auth_error"
    UNREACHABLE = "unreachable"
    ERROR = "error"


class SNMPPollingConfig(Base):
    """Per-router SNMP polling configuration."""

    __tablename__ = "snmp_polling_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    router_id: Mapped[int] = mapped_column(
        ForeignKey("routers.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # SNMP Version
    snmp_version: Mapped[SNMPVersion] = mapped_column(
        Enum(SNMPVersion),
        default=SNMPVersion.V2C,
    )

    # SNMPv2c settings
    community: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )  # Encrypted in DB

    # SNMPv3 settings
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    auth_protocol: Mapped[Optional[SNMPAuthProtocol]] = mapped_column(
        Enum(SNMPAuthProtocol),
        nullable=True,
    )
    auth_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )  # Encrypted
    priv_protocol: Mapped[Optional[SNMPPrivProtocol]] = mapped_column(
        Enum(SNMPPrivProtocol),
        nullable=True,
    )
    priv_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )  # Encrypted

    # Polling settings
    polling_interval_seconds: Mapped[int] = mapped_column(default=300)
    port: Mapped[int] = mapped_column(default=161)
    timeout_seconds: Mapped[int] = mapped_column(default=5)
    retries: Mapped[int] = mapped_column(default=2)

    # Status
    is_enabled: Mapped[bool] = mapped_column(default=True, index=True)
    last_polled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_poll_status: Mapped[Optional[PollStatus]] = mapped_column(
        Enum(PollStatus),
        nullable=True,
    )
    last_poll_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    router: Mapped["Router"] = relationship(backref="snmp_config", uselist=False)

    def __repr__(self) -> str:
        return f"<SNMPPollingConfig router_id={self.router_id} version={self.snmp_version.value}>"


# =============================================================================
# Device Metrics
# =============================================================================


class DeviceMetric(Base):
    """Device-level metrics (CPU, memory, uptime) collected via SNMP."""

    __tablename__ = "device_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    router_id: Mapped[int] = mapped_column(
        ForeignKey("routers.id", ondelete="CASCADE"),
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(index=True)

    # System metrics
    uptime_seconds: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    cpu_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memory_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memory_used_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    memory_total_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Aggregated traffic (all interfaces combined)
    total_rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    total_tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    total_rx_rate_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    total_tx_rate_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Active sessions (from MikroTik)
    active_ppp_sessions: Mapped[Optional[int]] = mapped_column(nullable=True)
    active_hotspot_sessions: Mapped[Optional[int]] = mapped_column(nullable=True)
    active_dhcp_leases: Mapped[Optional[int]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_device_metrics_router_timestamp", "router_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<DeviceMetric router_id={self.router_id} ts={self.timestamp}>"


# =============================================================================
# Interface Metrics
# =============================================================================


class InterfaceOperStatus(str, enum.Enum):
    """Interface operational status."""

    UP = "up"
    DOWN = "down"
    TESTING = "testing"
    UNKNOWN = "unknown"
    DORMANT = "dormant"
    NOT_PRESENT = "not_present"
    LOWER_LAYER_DOWN = "lower_layer_down"


class InterfaceMetric(Base):
    """Per-interface traffic metrics collected via SNMP."""

    __tablename__ = "interface_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    router_id: Mapped[int] = mapped_column(
        ForeignKey("routers.id", ondelete="CASCADE"),
        index=True,
    )
    interface_index: Mapped[int] = mapped_column(index=True)
    interface_name: Mapped[str] = mapped_column(String(100))
    timestamp: Mapped[datetime] = mapped_column(index=True)

    # Traffic counters (64-bit from ifHCInOctets/ifHCOutOctets)
    rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    rx_packets: Mapped[int] = mapped_column(BigInteger, default=0)
    tx_packets: Mapped[int] = mapped_column(BigInteger, default=0)

    # Error counters
    rx_errors: Mapped[int] = mapped_column(default=0)
    tx_errors: Mapped[int] = mapped_column(default=0)
    rx_discards: Mapped[int] = mapped_column(default=0)
    tx_discards: Mapped[int] = mapped_column(default=0)

    # Calculated rates (bits per second)
    rx_rate_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    tx_rate_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Interface status
    oper_status: Mapped[InterfaceOperStatus] = mapped_column(
        Enum(InterfaceOperStatus),
        default=InterfaceOperStatus.UNKNOWN,
    )
    admin_status: Mapped[InterfaceOperStatus] = mapped_column(
        Enum(InterfaceOperStatus),
        default=InterfaceOperStatus.UNKNOWN,
    )
    speed_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        Index(
            "ix_interface_metrics_router_if_ts",
            "router_id",
            "interface_index",
            "timestamp",
        ),
    )

    def __repr__(self) -> str:
        return f"<InterfaceMetric {self.interface_name} router={self.router_id}>"


# =============================================================================
# Interface State (Current Snapshot)
# =============================================================================


class InterfaceState(Base):
    """Current interface state - latest snapshot for quick lookups."""

    __tablename__ = "interface_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    router_id: Mapped[int] = mapped_column(
        ForeignKey("routers.id", ondelete="CASCADE"),
        index=True,
    )
    interface_index: Mapped[int]
    interface_name: Mapped[str] = mapped_column(String(100))
    interface_alias: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    interface_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Current state
    oper_status: Mapped[InterfaceOperStatus] = mapped_column(
        Enum(InterfaceOperStatus),
        default=InterfaceOperStatus.UNKNOWN,
    )
    admin_status: Mapped[InterfaceOperStatus] = mapped_column(
        Enum(InterfaceOperStatus),
        default=InterfaceOperStatus.UNKNOWN,
    )
    speed_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    mtu: Mapped[Optional[int]] = mapped_column(nullable=True)
    mac_address: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Latest counters
    last_rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    last_tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    last_rx_rate_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    last_tx_rate_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # State tracking
    last_state_change_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_polled_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Is this an uplink/WAN interface?
    is_uplink: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (
        Index(
            "ix_interface_states_router_if",
            "router_id",
            "interface_index",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<InterfaceState {self.interface_name} status={self.oper_status.value}>"


# =============================================================================
# Metric Rollups (Aggregated)
# =============================================================================


class MetricAggregation(str, enum.Enum):
    """Aggregation period for rollups."""

    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"


class InterfaceMetricRollup(Base):
    """Aggregated interface metrics for historical graphs."""

    __tablename__ = "interface_metric_rollups"

    id: Mapped[int] = mapped_column(primary_key=True)
    router_id: Mapped[int] = mapped_column(
        ForeignKey("routers.id", ondelete="CASCADE"),
        index=True,
    )
    interface_index: Mapped[int]
    aggregation: Mapped[MetricAggregation] = mapped_column(
        Enum(MetricAggregation),
        index=True,
    )
    period_start: Mapped[datetime] = mapped_column(index=True)

    # Aggregated traffic rates (bps)
    avg_rx_rate_bps: Mapped[int] = mapped_column(BigInteger, default=0)
    avg_tx_rate_bps: Mapped[int] = mapped_column(BigInteger, default=0)
    max_rx_rate_bps: Mapped[int] = mapped_column(BigInteger, default=0)
    max_tx_rate_bps: Mapped[int] = mapped_column(BigInteger, default=0)
    min_rx_rate_bps: Mapped[int] = mapped_column(BigInteger, default=0)
    min_tx_rate_bps: Mapped[int] = mapped_column(BigInteger, default=0)
    p95_rx_rate_bps: Mapped[int] = mapped_column(BigInteger, default=0)
    p95_tx_rate_bps: Mapped[int] = mapped_column(BigInteger, default=0)

    # Totals for the period
    total_rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    total_tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    # Error counts
    total_rx_errors: Mapped[int] = mapped_column(default=0)
    total_tx_errors: Mapped[int] = mapped_column(default=0)

    # Availability
    samples_count: Mapped[int] = mapped_column(default=0)
    uptime_percent: Mapped[float] = mapped_column(Float, default=100.0)

    __table_args__ = (
        Index(
            "ix_metric_rollup_lookup",
            "router_id",
            "interface_index",
            "aggregation",
            "period_start",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<InterfaceMetricRollup {self.aggregation.value} {self.period_start}>"


# =============================================================================
# Subscription Usage Metrics
# =============================================================================


class SubscriptionUsageMetric(Base):
    """Per-subscription daily usage aggregated from RADIUS accounting."""

    __tablename__ = "subscription_usage_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        index=True,
    )
    period_date: Mapped[date] = mapped_column(Date, index=True)

    # Usage totals
    download_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    upload_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    # Session stats
    session_count: Mapped[int] = mapped_column(default=0)
    session_duration_seconds: Mapped[int] = mapped_column(default=0)

    # Peak rates
    peak_download_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    peak_upload_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Average rates
    avg_download_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    avg_upload_bps: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        Index(
            "ix_sub_usage_lookup",
            "subscription_id",
            "period_date",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<SubscriptionUsageMetric sub={self.subscription_id} date={self.period_date}>"

    @property
    def total_gb(self) -> float:
        """Return total usage in GB."""
        return self.total_bytes / (1024 * 1024 * 1024)
