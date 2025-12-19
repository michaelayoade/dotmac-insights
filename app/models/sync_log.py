from __future__ import annotations

from sqlalchemy import String, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
import enum
from app.database import Base
from app.utils.datetime_utils import utc_now


class SyncStatus(enum.Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class SyncSource(enum.Enum):
    SPLYNX = "splynx"
    ERPNEXT = "erpnext"
    CHATWOOT = "chatwoot"


class SyncLog(Base):
    """Track sync operations for monitoring and debugging."""

    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Sync details
    source: Mapped[SyncSource] = mapped_column(Enum(SyncSource), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sync_type: Mapped[str] = mapped_column(String(50), default="incremental")

    # Status
    status: Mapped[SyncStatus] = mapped_column(Enum(SyncStatus), default=SyncStatus.STARTED, index=True)

    # Counts
    records_fetched: Mapped[int] = mapped_column(default=0)
    records_created: Mapped[int] = mapped_column(default=0)
    records_updated: Mapped[int] = mapped_column(default=0)
    records_failed: Mapped[int] = mapped_column(default=0)

    # Timing
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # For incremental syncs
    last_sync_cursor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<SyncLog {self.source.value}:{self.entity_type} - {self.status.value}>"

    def complete(self, status: SyncStatus = SyncStatus.COMPLETED) -> None:
        self.status = status
        self.completed_at = utc_now()
        if self.started_at:
            self.duration_seconds = int((self.completed_at - self.started_at).total_seconds())

    def fail(self, error_message: str, error_details: Optional[str] = None) -> None:
        self.status = SyncStatus.FAILED
        self.error_message = error_message
        self.error_details = error_details
        self.complete(SyncStatus.FAILED)
