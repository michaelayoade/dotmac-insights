"""Support SLA models: policies, business calendars, targets, and breach logs."""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, JSON, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.agent import Team


class SLATargetType(str, Enum):
    """Types of SLA targets."""
    FIRST_RESPONSE = "first_response"
    RESOLUTION = "resolution"
    NEXT_RESPONSE = "next_response"


class BusinessHourType(str, Enum):
    """Types of business hour calendars."""
    STANDARD = "standard"       # Fixed hours per day (e.g., 9-5 weekdays)
    TWENTY_FOUR_SEVEN = "24x7"  # 24/7 coverage
    CUSTOM = "custom"           # Fully custom schedule


class RoutingStrategy(str, Enum):
    """Agent assignment strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_BUSY = "least_busy"
    SKILL_BASED = "skill_based"
    LOAD_BALANCED = "load_balanced"
    MANUAL = "manual"


class BusinessCalendar(Base):
    """Business hours calendar for SLA calculations.

    Defines when business hours apply for SLA time calculations.
    Can be standard (same hours each weekday), 24x7, or fully custom.

    Schedule format for STANDARD/CUSTOM:
    {
        "mon": {"start": "09:00", "end": "17:00"},
        "tue": {"start": "09:00", "end": "17:00"},
        ...
        "sat": null,  # Closed
        "sun": null
    }
    """

    __tablename__ = "business_calendars"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Calendar type
    calendar_type: Mapped[str] = mapped_column(String(20), default=BusinessHourType.STANDARD.value)

    # Timezone for schedule interpretation
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # Schedule (JSON) - format depends on calendar_type
    schedule: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Flags
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    holidays: Mapped[List["BusinessCalendarHoliday"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan"
    )
    sla_policies: Mapped[List["SLAPolicy"]] = relationship(back_populates="calendar")

    def __repr__(self) -> str:
        return f"<BusinessCalendar {self.name} ({self.calendar_type})>"


class BusinessCalendarHoliday(Base):
    """Holidays that override business hours in a calendar."""

    __tablename__ = "business_calendar_holidays"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    calendar_id: Mapped[int] = mapped_column(
        ForeignKey("business_calendars.id", ondelete="CASCADE"), nullable=False, index=True
    )

    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # If true, recurs annually on same month/day
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    calendar: Mapped["BusinessCalendar"] = relationship(back_populates="holidays")

    def __repr__(self) -> str:
        return f"<BusinessCalendarHoliday {self.name} ({self.holiday_date})>"


class SLAPolicy(Base):
    """SLA policy defining response/resolution targets.

    Policies are matched to tickets based on conditions (priority, type, customer, etc.).
    Each policy can have multiple targets for different metrics (first response, resolution).

    Condition format: [{"field": "priority", "operator": "equals", "value": "urgent"}, ...]
    """

    __tablename__ = "sla_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Business calendar (optional - if null, uses 24x7)
    calendar_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("business_calendars.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Conditions to match tickets (JSON array)
    # Example: [{"field": "priority", "operator": "equals", "value": "urgent"}]
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Flags
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)  # Fallback policy
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)  # Lower = higher priority
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    calendar: Mapped[Optional["BusinessCalendar"]] = relationship(back_populates="sla_policies")
    targets: Mapped[List["SLATarget"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan"
    )
    breach_logs: Mapped[List["SLABreachLog"]] = relationship(back_populates="policy")

    def __repr__(self) -> str:
        return f"<SLAPolicy {self.name}>"


class SLATarget(Base):
    """Specific SLA target within a policy.

    Each target defines a response/resolution time for a specific priority level.
    For example: "Urgent tickets must have first response within 1 hour".
    """

    __tablename__ = "sla_targets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    policy_id: Mapped[int] = mapped_column(
        ForeignKey("sla_policies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # What type of SLA target (first response, resolution, etc.)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Which priority this target applies to (low, medium, high, urgent)
    # If null, applies to all priorities not specifically defined
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    # Target time in hours (can be fractional, e.g., 0.5 = 30 minutes)
    target_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Warning threshold as percentage (e.g., 80 = warn at 80% of time elapsed)
    warning_threshold_pct: Mapped[int] = mapped_column(Integer, default=80)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    policy: Mapped["SLAPolicy"] = relationship(back_populates="targets")

    def __repr__(self) -> str:
        return f"<SLATarget {self.target_type} {self.priority}: {self.target_hours}h>"


class SLABreachLog(Base):
    """Log of SLA breaches for reporting and analytics."""

    __tablename__ = "sla_breach_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # References
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("sla_policies.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # What breached
    target_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # SLA details
    target_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Timestamps
    breached_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Warning tracking
    was_warned: Mapped[bool] = mapped_column(Boolean, default=False)
    warned_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    ticket: Mapped["Ticket"] = relationship()
    policy: Mapped[Optional["SLAPolicy"]] = relationship(back_populates="breach_logs")

    def __repr__(self) -> str:
        return f"<SLABreachLog ticket={self.ticket_id} {self.target_type} at {self.breached_at}>"


class RoutingRule(Base):
    """Rules for automatic ticket assignment to agents/teams.

    Rules are evaluated in priority order. The first matching rule's strategy
    is used to assign the ticket. If no rules match, fallback behavior applies.

    Condition format: [{"field": "ticket_type", "operator": "equals", "value": "billing"}, ...]
    """

    __tablename__ = "routing_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Target team for this rule (optional - can be agent-level routing)
    team_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Routing strategy
    strategy: Mapped[str] = mapped_column(String(30), default=RoutingStrategy.ROUND_ROBIN.value)

    # Conditions to match tickets (JSON array)
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Priority (lower = evaluated first)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)

    # Flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Fallback team if no agent available
    fallback_team_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    team: Mapped[Optional["Team"]] = relationship(foreign_keys=[team_id])
    fallback_team: Mapped[Optional["Team"]] = relationship(foreign_keys=[fallback_team_id])

    def __repr__(self) -> str:
        return f"<RoutingRule {self.name} ({self.strategy})>"


class RoutingRoundRobinState(Base):
    """State tracking for round-robin assignment.

    Keeps track of which agent was last assigned for each team
    to ensure fair distribution.
    """

    __tablename__ = "routing_round_robin_state"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    # Last assigned agent ID
    last_agent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )

    # When this was last updated
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<RoutingRoundRobinState team={self.team_id} last_agent={self.last_agent_id}>"
