"""
Sync Schedule Model

Stores user-configurable sync schedules that can be managed through the admin UI.
These work alongside the hard-coded Celery beat schedules.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Boolean, Integer, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now


class SyncSchedule(Base):
    """
    User-configurable sync schedule.

    Allows admins to define and manage sync schedules through the UI.
    These schedules work alongside the built-in Celery beat schedules.
    """

    __tablename__ = "sync_schedules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Schedule identification
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Task configuration
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)  # Celery task name
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)  # Cron syntax
    kwargs: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)  # Task arguments

    # Schedule state
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # Built-in vs user-created

    # Execution tracking
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<SyncSchedule {self.name}: {self.task_name} ({self.cron_expression})>"

    def mark_run_started(self) -> None:
        """Mark that a scheduled run has started."""
        self.last_run_at = utc_now()
        self.last_run_status = "running"
        self.run_count += 1

    def mark_run_success(self) -> None:
        """Mark that a scheduled run completed successfully."""
        self.last_run_status = "success"
        self.last_error = None

    def mark_run_failed(self, error: str) -> None:
        """Mark that a scheduled run failed."""
        self.last_run_status = "failed"
        self.last_error = error

    @property
    def status(self) -> str:
        """Get current status for display."""
        if not self.is_enabled:
            return "disabled"
        if self.last_run_status:
            return self.last_run_status
        return "pending"
