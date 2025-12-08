from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, Boolean
from datetime import datetime
import enum
from app.database import Base


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

    id = Column(Integer, primary_key=True, index=True)

    # Sync details
    source = Column(Enum(SyncSource), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False)  # customers, invoices, etc.
    sync_type = Column(String(50), default="incremental")  # full, incremental

    # Status
    status = Column(Enum(SyncStatus), default=SyncStatus.STARTED, index=True)

    # Counts
    records_fetched = Column(Integer, default=0)
    records_created = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)  # Full stack trace or details

    # For incremental syncs
    last_sync_cursor = Column(String(255), nullable=True)  # Last ID or timestamp synced

    def __repr__(self):
        return f"<SyncLog {self.source.value}:{self.entity_type} - {self.status.value}>"

    def complete(self, status: SyncStatus = SyncStatus.COMPLETED):
        self.status = status
        self.completed_at = datetime.utcnow()
        if self.started_at:
            self.duration_seconds = int((self.completed_at - self.started_at).total_seconds())

    def fail(self, error_message: str, error_details: str = None):
        self.status = SyncStatus.FAILED
        self.error_message = error_message
        self.error_details = error_details
        self.complete(SyncStatus.FAILED)
