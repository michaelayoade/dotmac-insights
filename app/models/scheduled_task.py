"""Scheduled task model for tracking delayed Celery tasks."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base

if TYPE_CHECKING:
    from app.models.auth import User


class ScheduledTaskStatus(enum.Enum):
    """Status of a scheduled task."""
    SCHEDULED = "scheduled"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ScheduledTask(Base):
    """
    Tracks Celery tasks scheduled for future execution.

    This model enables:
    - Visibility into pending scheduled tasks
    - Cancellation of scheduled tasks via Celery revoke
    - Audit trail of scheduled task execution
    - Association with source entities for context

    Example use cases:
    - "Remind me about this lead in 3 days"
    - "Auto-close ticket if no response in 7 days"
    - "Escalate approval if not acted on in 24 hours"
    """

    __tablename__ = "scheduled_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Celery reference
    celery_task_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="Celery AsyncResult ID"
    )
    task_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Celery task name (e.g., scheduled.send_reminder)"
    )

    # Schedule
    scheduled_for: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="When the task should execute"
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="When the task actually executed"
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default="scheduled",
        comment="scheduled, executed, cancelled, failed"
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    cancelled_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Context
    source_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Entity type this task relates to"
    )
    source_id: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Entity ID this task relates to"
    )
    payload: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Task arguments/kwargs"
    )
    result: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Task return value"
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if failed"
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    cancelled_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[cancelled_by_id],
        lazy="select"
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy="select"
    )

    __table_args__ = (
        Index(
            "ix_scheduled_tasks_status_scheduled_for",
            "status",
            "scheduled_for",
            postgresql_where="status = 'scheduled'"
        ),
        Index(
            "ix_scheduled_tasks_source",
            "source_type",
            "source_id",
            postgresql_where="source_type IS NOT NULL"
        ),
        Index(
            "ix_scheduled_tasks_celery_task_id",
            "celery_task_id",
            unique=True
        ),
        Index(
            "ix_scheduled_tasks_task_name",
            "task_name",
            "status"
        ),
    )

    @property
    def is_pending(self) -> bool:
        """Check if task is still scheduled to run."""
        return self.status == ScheduledTaskStatus.SCHEDULED.value

    @property
    def can_cancel(self) -> bool:
        """Check if task can be cancelled."""
        return self.status == ScheduledTaskStatus.SCHEDULED.value

    @property
    def time_until_execution(self) -> Optional[float]:
        """Get seconds until scheduled execution."""
        if self.status != ScheduledTaskStatus.SCHEDULED.value:
            return None
        delta = self.scheduled_for - datetime.utcnow()
        return max(0, delta.total_seconds())

    def __repr__(self) -> str:
        return f"<ScheduledTask(id={self.id}, task={self.task_name}, status={self.status}, eta={self.scheduled_for})>"
