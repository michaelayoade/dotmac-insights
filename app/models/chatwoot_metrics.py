"""Chatwoot metrics snapshot models for storing synced report data."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, ForeignKey, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.omni import OmniChannel
    from app.models.agent import Team


class MetricPeriod(str, Enum):
    """Time period granularity for metrics."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class MetricLevel(str, Enum):
    """Aggregation level for metrics."""
    ACCOUNT = "account"
    AGENT = "agent"
    INBOX = "inbox"
    TEAM = "team"


class ChatwootMetricSnapshot(Base):
    """Snapshot of Chatwoot metrics for a specific time period.

    Stores aggregated metrics from Chatwoot reports API for analytics
    and dashboard purposes. Supports multiple aggregation levels
    (account, agent, inbox, team) and time periods (hourly, daily, etc).
    """

    __tablename__ = "chatwoot_metric_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Time dimensions
    period_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(nullable=False)

    # Entity dimensions - what level this metric is for
    metric_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Foreign keys - nullable based on metric_level
    agent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    inbox_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("omni_channels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    team_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Chatwoot's own IDs (for reference even if FK is null)
    chatwoot_agent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    chatwoot_inbox_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chatwoot_team_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Conversation metrics
    conversations_count: Mapped[int] = mapped_column(Integer, default=0)
    incoming_messages_count: Mapped[int] = mapped_column(Integer, default=0)
    outgoing_messages_count: Mapped[int] = mapped_column(Integer, default=0)
    resolved_count: Mapped[int] = mapped_column(Integer, default=0)

    # Time metrics (in seconds)
    avg_first_response_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_resolution_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # CSAT metrics
    csat_total_responses: Mapped[int] = mapped_column(Integer, default=0)
    csat_positive_responses: Mapped[int] = mapped_column(Integer, default=0)
    csat_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    # Raw metrics JSON for additional data from API
    raw_metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Audit
    synced_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    agent: Mapped[Optional["Employee"]] = relationship(foreign_keys=[agent_id])
    inbox: Mapped[Optional["OmniChannel"]] = relationship(foreign_keys=[inbox_id])
    team: Mapped[Optional["Team"]] = relationship(foreign_keys=[team_id])

    def __repr__(self) -> str:
        return f"<ChatwootMetricSnapshot {self.period_type} {self.metric_level} {self.period_start}>"
