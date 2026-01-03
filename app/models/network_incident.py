"""Network Incident Model - Outage and incident management."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from enum import Enum

from sqlalchemy import BigInteger, String, Text, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


class IncidentSeverity(str, Enum):
    """Incident severity levels."""
    MAINTENANCE = "maintenance"  # Scheduled maintenance
    MINOR = "minor"  # Limited impact
    MAJOR = "major"  # Significant impact
    CRITICAL = "critical"  # Service outage


class IncidentStatus(str, Enum):
    """Incident status workflow."""
    INVESTIGATING = "investigating"  # Initial detection
    IDENTIFIED = "identified"  # Root cause identified
    MONITORING = "monitoring"  # Fix applied, monitoring
    RESOLVED = "resolved"  # Fully resolved
    SCHEDULED = "scheduled"  # For planned maintenance


class NetworkIncident(Base):
    """Network outage or incident tracking.

    Tracks network incidents, affected infrastructure, and customer impact.
    Supports status page integration and post-mortem analysis.
    """

    __tablename__ = "network_incidents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Basic info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    severity: Mapped[str] = mapped_column(String(20), default=IncidentSeverity.MINOR.value, index=True)
    status: Mapped[str] = mapped_column(String(20), default=IncidentStatus.INVESTIGATING.value, index=True)
    incident_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # network, hardware, power, etc.

    # Affected infrastructure (JSON arrays)
    affected_pop_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)
    affected_router_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)
    affected_interface_names: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Customer impact
    affected_subscription_count: Mapped[int] = mapped_column(default=0)
    estimated_customer_count: Mapped[int] = mapped_column(default=0)
    estimated_revenue_impact: Mapped[Optional[float]] = mapped_column(nullable=True)

    # Timeline
    started_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    detected_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    scheduled_end_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # For maintenance

    # Root cause analysis
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Resolution
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_time_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Public communication
    public_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    public_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(default=False)  # Show on status page

    # Automation flags
    auto_detected: Mapped[bool] = mapped_column(default=False)  # From SNMP/monitoring
    auto_resolved: Mapped[bool] = mapped_column(default=False)  # Auto-detected recovery

    # Assignment
    assigned_to_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
        index=True,
    )

    # External references
    external_ticket_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_alert_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assigned_to: Mapped[Optional["Employee"]] = relationship(foreign_keys=[assigned_to_id])
    updates: Mapped[List["IncidentUpdate"]] = relationship(back_populates="incident", order_by="IncidentUpdate.created_at")

    __table_args__ = (
        Index("ix_network_incidents_status_severity", "status", "severity"),
        Index("ix_network_incidents_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<NetworkIncident {self.id}: {self.title} [{self.status}]>"

    @property
    def duration_minutes(self) -> Optional[int]:
        """Calculate incident duration in minutes."""
        if self.resolved_at and self.started_at:
            delta = self.resolved_at - self.started_at
            return int(delta.total_seconds() / 60)
        return None

    @property
    def is_active(self) -> bool:
        """Check if incident is still active."""
        return self.status not in [IncidentStatus.RESOLVED.value]


class IncidentUpdate(Base):
    """Status updates for incidents.

    Tracks the progression of incident investigation and resolution.
    """

    __tablename__ = "incident_updates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Parent incident
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("network_incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Update content
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Public visibility
    is_public: Mapped[bool] = mapped_column(default=False)
    public_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Author
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Relationship
    incident: Mapped["NetworkIncident"] = relationship(back_populates="updates")

    def __repr__(self) -> str:
        return f"<IncidentUpdate {self.incident_id}: {self.status} @ {self.created_at}>"


class IncidentAffectedSubscription(Base):
    """Track specific subscriptions affected by an incident.

    Used for customer notification and SLA credit calculation.
    """

    __tablename__ = "incident_affected_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    incident_id: Mapped[int] = mapped_column(
        ForeignKey("network_incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Impact details
    impact_start: Mapped[datetime] = mapped_column(nullable=False)
    impact_end: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    downtime_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Notification status
    notified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    notification_channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # SLA credit
    sla_credit_applied: Mapped[bool] = mapped_column(default=False)
    credit_amount: Mapped[Optional[float]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_incident_affected_subs_incident_sub", "incident_id", "subscription_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<IncidentAffectedSubscription incident={self.incident_id} sub={self.subscription_id}>"
