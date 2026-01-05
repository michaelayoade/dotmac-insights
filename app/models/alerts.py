"""Alert Models - Device and system-level alerting.

This module provides a general-purpose alerting system for:
- Device-level alerts (CPU, memory, temperature, down/up)
- Interface operational status (not covered by TrafficThreshold)
- System alerts (disk, services)

Note: Traffic threshold alerts are handled by traffic_metrics.TrafficAlert.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from enum import Enum

from sqlalchemy import BigInteger, String, Text, ForeignKey, Index, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.router import Router
    from app.models.pop import Pop
    from app.models.employee import Employee


class AlertType(str, Enum):
    """Types of alerts that can be generated."""
    # Device-level
    DEVICE_DOWN = "device_down"
    DEVICE_UP = "device_up"  # Auto-recovery notification
    DEVICE_HIGH_CPU = "device_high_cpu"
    DEVICE_HIGH_MEMORY = "device_high_memory"
    DEVICE_HIGH_TEMPERATURE = "device_high_temperature"
    DEVICE_REBOOT_DETECTED = "device_reboot_detected"

    # Interface-level (operational, not traffic)
    INTERFACE_DOWN = "interface_down"
    INTERFACE_UP = "interface_up"
    INTERFACE_FLAPPING = "interface_flapping"
    INTERFACE_ERRORS = "interface_errors"

    # Connectivity
    SNMP_UNREACHABLE = "snmp_unreachable"
    API_UNREACHABLE = "api_unreachable"

    # System
    DISK_HIGH_USAGE = "disk_high_usage"
    SERVICE_DOWN = "service_down"

    # Custom/manual
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    @classmethod
    def priority(cls, severity: str) -> int:
        """Return numeric priority (lower = more urgent)."""
        return {
            cls.CRITICAL.value: 1,
            cls.WARNING.value: 2,
            cls.INFO.value: 3,
        }.get(severity, 99)


class AlertStatus(str, Enum):
    """Alert lifecycle status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertRule(Base):
    """Configurable alert thresholds and conditions.

    Rules define when to trigger alerts based on metric values.
    Can be scoped globally, per-POP, or per-router.
    """

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Rule identification
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Alert type and severity
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default=AlertSeverity.WARNING.value)

    # Scope (null = global, otherwise scoped to specific entity)
    router_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("routers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    pop_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pops.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    interface_pattern: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Regex for interface names

    # Threshold configuration
    threshold_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    threshold_operator: Mapped[str] = mapped_column(String(10), default="gt")  # gt, lt, gte, lte, eq, ne

    # Sustained condition (must breach for N seconds before alerting)
    threshold_duration_seconds: Mapped[int] = mapped_column(default=0)

    # Alert rate limiting
    cooldown_seconds: Mapped[int] = mapped_column(default=300)  # Min time between repeat alerts

    # Notification configuration (JSON for flexibility)
    notification_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"channels": ["email", "slack"], "recipients": ["noc@company.com"]}

    # Status
    is_enabled: Mapped[bool] = mapped_column(default=True, index=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    router: Mapped[Optional["Router"]] = relationship(foreign_keys=[router_id])
    pop: Mapped[Optional["Pop"]] = relationship(foreign_keys=[pop_id])
    alerts: Mapped[List["Alert"]] = relationship(back_populates="rule", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_alert_rules_enabled_type", "is_enabled", "alert_type"),
        Index("ix_alert_rules_scope", "router_id", "pop_id"),
    )

    def __repr__(self) -> str:
        return f"<AlertRule {self.name}: {self.alert_type} {self.threshold_operator} {self.threshold_value}>"

    def matches_threshold(self, value: float) -> bool:
        """Check if a value matches this rule's threshold condition."""
        ops = {
            "gt": lambda v, t: v > t,
            "lt": lambda v, t: v < t,
            "gte": lambda v, t: v >= t,
            "lte": lambda v, t: v <= t,
            "eq": lambda v, t: v == t,
            "ne": lambda v, t: v != t,
        }
        op_func = ops.get(self.threshold_operator, ops["gt"])
        return op_func(value, float(self.threshold_value))


class Alert(Base):
    """Active and historical alerts.

    Tracks individual alert instances from trigger to resolution.
    Supports acknowledgement workflow and auto-resolution.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    # Source rule (optional - manual/custom alerts may not have a rule)
    rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Alert classification
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=AlertStatus.ACTIVE.value, index=True)

    # Affected entity
    router_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("routers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    pop_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pops.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    interface_index: Mapped[Optional[int]] = mapped_column(nullable=True)
    interface_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Alert content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Metric that triggered the alert
    metric_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metric_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    threshold_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)

    # Timeline
    triggered_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    first_occurrence_at: Mapped[datetime] = mapped_column(nullable=False)  # For flapping detection
    last_occurrence_at: Mapped[datetime] = mapped_column(nullable=False)
    occurrence_count: Mapped[int] = mapped_column(default=1)  # How many times condition hit

    # Acknowledgement
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    acknowledged_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )
    acknowledgement_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Resolution
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_resolved: Mapped[bool] = mapped_column(default=False)  # True if metric returned to normal

    # Incident linkage
    incident_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("network_incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Suppression
    suppressed_until: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    suppression_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Notification tracking
    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    notification_channels: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Extra context
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    rule: Mapped[Optional["AlertRule"]] = relationship(back_populates="alerts")
    router: Mapped[Optional["Router"]] = relationship(foreign_keys=[router_id])
    pop: Mapped[Optional["Pop"]] = relationship(foreign_keys=[pop_id])
    acknowledged_by: Mapped[Optional["Employee"]] = relationship(foreign_keys=[acknowledged_by_id])
    resolved_by: Mapped[Optional["Employee"]] = relationship(foreign_keys=[resolved_by_id])

    __table_args__ = (
        Index("ix_alerts_status_severity", "status", "severity"),
        Index("ix_alerts_active_router", "status", "router_id"),
        Index("ix_alerts_triggered_at", "triggered_at"),
    )

    def __repr__(self) -> str:
        return f"<Alert {self.id}: {self.alert_type} [{self.status}] @ {self.triggered_at}>"

    @property
    def is_active(self) -> bool:
        """Check if alert is still active (not resolved/suppressed)."""
        return self.status == AlertStatus.ACTIVE.value

    @property
    def is_acknowledged(self) -> bool:
        """Check if alert has been acknowledged."""
        return self.status == AlertStatus.ACKNOWLEDGED.value or self.acknowledged_at is not None

    @property
    def duration_seconds(self) -> Optional[int]:
        """Get duration of alert in seconds (None if still active)."""
        if self.resolved_at:
            return int((self.resolved_at - self.triggered_at).total_seconds())
        return None

    @property
    def is_suppressed(self) -> bool:
        """Check if alert is currently suppressed."""
        if self.status == AlertStatus.SUPPRESSED.value:
            return True
        if self.suppressed_until and datetime.utcnow() < self.suppressed_until:
            return True
        return False


class AlertEscalation(Base):
    """Alert escalation configuration.

    Defines escalation paths when alerts aren't acknowledged/resolved.
    """

    __tablename__ = "alert_escalations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Rule this escalation applies to (null = default for all)
    rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Escalation level (1 = first escalation, 2 = second, etc.)
    level: Mapped[int] = mapped_column(nullable=False)

    # Timing
    escalate_after_minutes: Mapped[int] = mapped_column(nullable=False)  # Minutes since trigger

    # Notification
    notification_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Example: {"channels": ["email", "sms"], "recipients": ["manager@company.com"]}

    # Status
    is_enabled: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        Index("ix_alert_escalations_rule_level", "rule_id", "level", unique=True),
    )

    def __repr__(self) -> str:
        return f"<AlertEscalation rule={self.rule_id} level={self.level}>"


class AlertSuppression(Base):
    """Temporary alert suppression (maintenance windows).

    Suppress alerts during maintenance to prevent noise.
    """

    __tablename__ = "alert_suppressions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Suppression scope
    router_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("routers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    pop_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pops.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    alert_types: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # null = all types

    # Time window
    starts_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Reason
    reason: Mapped[str] = mapped_column(String(255), nullable=False)

    # Related incident (for planned maintenance)
    incident_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("network_incidents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        Index("ix_alert_suppressions_active", "starts_at", "ends_at"),
    )

    def __repr__(self) -> str:
        return f"<AlertSuppression {self.starts_at} - {self.ends_at}>"

    def is_active(self) -> bool:
        """Check if suppression is currently active."""
        now = datetime.utcnow()
        return self.starts_at <= now <= self.ends_at

    def matches_alert(self, alert_type: str, router_id: Optional[int], pop_id: Optional[int]) -> bool:
        """Check if this suppression applies to a given alert."""
        # Check type
        if self.alert_types and alert_type not in self.alert_types:
            return False

        # Check scope
        if self.router_id and self.router_id != router_id:
            return False
        if self.pop_id and self.pop_id != pop_id:
            return False

        return True
