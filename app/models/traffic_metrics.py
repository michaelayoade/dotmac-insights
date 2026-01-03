"""Traffic Metrics Model - Real-time bandwidth monitoring."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, String, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.router import Router
    from app.models.subscription import Subscription


class TrafficMetric(Base):
    """Real-time traffic metrics per interface.

    Stores traffic samples polled from routers via SNMP or API.
    Used for bandwidth monitoring, graphing, and alerting.
    """

    __tablename__ = "traffic_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    # Source device
    router_id: Mapped[int] = mapped_column(
        ForeignKey("routers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Interface identification
    interface: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    interface_index: Mapped[Optional[int]] = mapped_column(nullable=True)
    interface_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Optional link to subscription (for per-customer metrics)
    subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Timestamp of measurement
    timestamp: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Cumulative counters (from SNMP ifInOctets/ifOutOctets)
    rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    # Calculated rates (bits per second)
    rx_rate: Mapped[int] = mapped_column(BigInteger, default=0)  # bps
    tx_rate: Mapped[int] = mapped_column(BigInteger, default=0)  # bps

    # Packet counters
    rx_packets: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    tx_packets: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Error counters
    rx_errors: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    tx_errors: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    rx_drops: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    tx_drops: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Interface status
    oper_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # up, down
    admin_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Aggregation level
    aggregation: Mapped[str] = mapped_column(String(20), default="raw")  # raw, hourly, daily

    # Relationships
    router: Mapped["Router"] = relationship(backref="traffic_metrics")
    subscription: Mapped[Optional["Subscription"]] = relationship(backref="traffic_metrics")

    __table_args__ = (
        Index("ix_traffic_metrics_router_timestamp", "router_id", "timestamp"),
        Index("ix_traffic_metrics_interface_timestamp", "interface", "timestamp"),
        Index("ix_traffic_metrics_aggregation_timestamp", "aggregation", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<TrafficMetric {self.interface} @ {self.timestamp}>"


class TrafficThreshold(Base):
    """Traffic threshold configuration for alerting.

    Define thresholds per interface/router for bandwidth alerts.
    """

    __tablename__ = "traffic_thresholds"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Scope
    router_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("routers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    interface: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Threshold configuration
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)  # rx_rate, tx_rate, errors
    operator: Mapped[str] = mapped_column(String(10), default="gt")  # gt, lt, eq
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(default=300)  # Sustained for N seconds

    # Alert configuration
    severity: Mapped[str] = mapped_column(String(20), default="warning")  # info, warning, critical
    notification_channels: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # JSON array

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    trigger_count: Mapped[int] = mapped_column(default=0)

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TrafficThreshold {self.name}: {self.metric} {self.operator} {self.value}>"


class TrafficAlert(Base):
    """Triggered traffic alerts.

    Records when traffic thresholds are breached.
    """

    __tablename__ = "traffic_alerts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Links
    threshold_id: Mapped[int] = mapped_column(
        ForeignKey("traffic_thresholds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    router_id: Mapped[int] = mapped_column(
        ForeignKey("routers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Alert details
    interface: Mapped[str] = mapped_column(String(100), nullable=False)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    threshold_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actual_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active, acknowledged, resolved
    acknowledged_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Timestamps
    triggered_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_traffic_alerts_status_triggered", "status", "triggered_at"),
    )

    def __repr__(self) -> str:
        return f"<TrafficAlert {self.interface} {self.severity} @ {self.triggered_at}>"
