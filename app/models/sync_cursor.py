from __future__ import annotations

from sqlalchemy import String, Text, Enum, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from typing import Optional, Union
from app.database import Base
from app.models.sync_log import SyncSource
from app.utils.datetime_utils import utc_now


def utcnow() -> datetime:
    """Get current UTC time as timezone-aware datetime.

    Deprecated: Use utc_now from app.utils.datetime_utils instead.
    """
    return utc_now()


def parse_datetime(value: Union[str, datetime, int, float, None]) -> Optional[datetime]:
    """Parse various datetime formats to datetime object.

    Handles:
    - datetime objects (passthrough)
    - ISO format strings (YYYY-MM-DD HH:MM:SS or YYYY-MM-DDTHH:MM:SS)
    - Date strings (YYYY-MM-DD)
    - Unix timestamps (int or float)
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        # Try various formats
        for fmt in [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
        ]:
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


class SyncCursor(Base):
    """Track incremental sync cursors per source and entity type.

    This allows each entity type to maintain its own cursor for incremental syncs,
    enabling efficient delta fetches instead of full re-syncs.
    """

    __tablename__ = "sync_cursors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Source and entity identification
    source: Mapped[SyncSource] = mapped_column(Enum(SyncSource), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Cursor values - store various cursor types (all datetime for proper comparison)
    last_sync_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Last processed ID
    last_page: Mapped[Optional[int]] = mapped_column(nullable=True)  # For paginated APIs
    cursor_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Generic cursor (JSON)

    # Metadata
    records_synced: Mapped[int] = mapped_column(default=0)  # Total records synced since cursor set
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint('source', 'entity_type', name='uix_sync_cursor_source_entity'),
    )

    def __repr__(self) -> str:
        return f"<SyncCursor {self.source.value}:{self.entity_type}>"

    def update_cursor(
        self,
        timestamp: Optional[datetime] = None,
        modified_at: Union[str, datetime, int, float, None] = None,
        last_id: Optional[str] = None,
        cursor_value: Optional[str] = None,
        records_count: int = 0,
    ):
        """Update cursor values after successful sync.

        Args:
            timestamp: Direct datetime value for last_sync_timestamp
            modified_at: Value to parse and store as last_modified_at (accepts various formats)
            last_id: Last processed record ID
            cursor_value: Generic cursor value (JSON string)
            records_count: Number of records processed in this sync
        """
        if timestamp:
            self.last_sync_timestamp = timestamp
        if modified_at is not None:
            # Parse to datetime for proper comparison
            self.last_modified_at = parse_datetime(modified_at)
        if last_id:
            self.last_id = last_id
        if cursor_value:
            self.cursor_value = cursor_value
        self.records_synced += records_count
        self.last_sync_at = utcnow()

    def reset(self):
        """Reset cursor for full sync."""
        self.last_sync_timestamp = None
        self.last_modified_at = None
        self.last_id = None
        self.last_page = None
        self.cursor_value = None
        self.records_synced = 0


class FailedSyncRecord(Base):
    """Dead Letter Queue for failed sync records.

    Stores records that failed to sync for later retry or manual investigation.
    """

    __tablename__ = "failed_sync_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Source and entity identification
    source: Mapped[SyncSource] = mapped_column(Enum(SyncSource), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Failed record data
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON serialized record
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(default=0)
    max_retries: Mapped[int] = mapped_column(default=3)
    last_retry_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)

    # Status
    is_resolved: Mapped[bool] = mapped_column(default=False, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<FailedSyncRecord {self.source.value}:{self.entity_type} id={self.external_id}>"

    def mark_retry(self):
        """Mark that a retry was attempted."""
        self.retry_count += 1
        self.last_retry_at = utc_now()

    def mark_resolved(self, notes: Optional[str] = None):
        """Mark the record as resolved."""
        self.is_resolved = True
        self.resolved_at = utc_now()
        self.resolution_notes = notes

    @property
    def can_retry(self) -> bool:
        """Check if this record can be retried."""
        return not self.is_resolved and self.retry_count < self.max_retries
