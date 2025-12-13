"""Support automation models: rules, triggers, actions, and logs."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class AutomationTrigger(str, Enum):
    """Events that can trigger automation rules."""
    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    TICKET_ASSIGNED = "ticket_assigned"
    TICKET_REPLIED = "ticket_replied"
    TICKET_STATUS_CHANGED = "ticket_status_changed"
    SLA_WARNING = "sla_warning"
    SLA_BREACHED = "sla_breached"
    TICKET_IDLE = "ticket_idle"
    CUSTOMER_REPLIED = "customer_replied"
    TICKET_ESCALATED = "ticket_escalated"


class AutomationActionType(str, Enum):
    """Actions that automation rules can perform."""
    SET_PRIORITY = "set_priority"
    SET_STATUS = "set_status"
    ASSIGN_AGENT = "assign_agent"
    ASSIGN_TEAM = "assign_team"
    ADD_TAG = "add_tag"
    REMOVE_TAG = "remove_tag"
    SEND_NOTIFICATION = "send_notification"
    SEND_EMAIL = "send_email"
    ADD_COMMENT = "add_comment"
    ESCALATE = "escalate"
    UPDATE_FIELD = "update_field"
    WEBHOOK = "webhook"


class ConditionOperator(str, Enum):
    """Operators for condition evaluation."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_OR_EQUAL = "less_or_equal"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    REGEX_MATCH = "regex_match"


class AutomationRule(Base):
    """Automation rules that execute actions based on triggers and conditions.

    Rules are evaluated when a trigger event occurs. If all conditions match,
    the configured actions are executed in order. Rules with lower priority
    numbers are evaluated first.

    Condition format: [{"field": "priority", "operator": "equals", "value": "urgent"}, ...]
    Action format: [{"type": "assign_team", "params": {"team_id": 1}}, ...]
    """

    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Rule identification
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Trigger event
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Conditions to match (JSON array)
    # Example: [{"field": "priority", "operator": "equals", "value": "urgent"}]
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Actions to execute (JSON array)
    # Example: [{"type": "assign_team", "params": {"team_id": 1}}]
    actions: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Execution control
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)  # Lower = higher priority
    stop_processing: Mapped[bool] = mapped_column(Boolean, default=False)  # Stop other rules after this

    # Rate limiting (optional)
    max_executions_per_hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Execution stats
    execution_count: Mapped[int] = mapped_column(Integer, default=0)
    last_executed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    logs: Mapped[List["AutomationLog"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AutomationRule {self.name} ({self.trigger})>"


class AutomationLog(Base):
    """Log of automation rule executions.

    Records each time an automation rule is evaluated and executed,
    including which conditions matched and which actions were performed.
    """

    __tablename__ = "automation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # References
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("automation_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Trigger that fired
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # What matched and what was executed
    conditions_matched: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    actions_executed: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Result
    success: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Performance
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Relationships
    rule: Mapped["AutomationRule"] = relationship(back_populates="logs")
    ticket: Mapped["Ticket"] = relationship()

    def __repr__(self) -> str:
        return f"<AutomationLog rule={self.rule_id} ticket={self.ticket_id} success={self.success}>"
