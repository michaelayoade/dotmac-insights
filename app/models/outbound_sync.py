"""
Outbound Sync Log Model

Tracks all outbound synchronization operations to external systems
(Splynx, ERPNext, etc.) for audit, idempotency, and retry purposes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from enum import Enum

from sqlalchemy import String, Integer, Text, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.datetime_utils import utc_now


class SyncStatus(str, Enum):
    """Status of a sync operation."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # Skipped due to idempotency (no change)


class SyncOperation(str, Enum):
    """Type of sync operation."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class TargetSystem(str, Enum):
    """External system being synced to."""
    SPLYNX = "splynx"
    ERPNEXT = "erpnext"
    CHATWOOT = "chatwoot"
    ZOHO = "zoho"


class OutboundSyncLog(Base):
    """
    Log of outbound sync operations.

    Used for:
    - Idempotency: Prevent duplicate syncs using idempotency_key
    - Audit: Track what was synced and when
    - Retry: Track failed syncs for retry
    - Debugging: Store request/response for troubleshooting
    """

    __tablename__ = "outbound_sync_log"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # What entity was synced
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Where it was synced to
    target_system: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # What operation
    operation: Mapped[str] = mapped_column(String(20), nullable=False)

    # Idempotency
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    payload_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Request/Response for debugging
    request_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<OutboundSyncLog {self.entity_type}:{self.entity_id} → {self.target_system} ({self.status})>"

    @classmethod
    def create_pending(
        cls,
        entity_type: str,
        entity_id: int,
        target_system: str,
        operation: str,
        idempotency_key: str,
        payload_hash: str,
        request_payload: Optional[dict] = None,
    ) -> "OutboundSyncLog":
        """Create a new pending sync log entry."""
        return cls(
            entity_type=entity_type,
            entity_id=entity_id,
            target_system=target_system,
            operation=operation,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            status=SyncStatus.PENDING.value,
            request_payload=request_payload,
            created_at=utc_now(),
        )

    def mark_success(self, external_id: Optional[str] = None, response: Optional[dict] = None):
        """Mark this sync as successful."""
        self.status = SyncStatus.SUCCESS.value
        self.external_id = external_id
        self.response_payload = response
        self.completed_at = utc_now()

    def mark_failed(self, error: str, response: Optional[dict] = None):
        """Mark this sync as failed."""
        self.status = SyncStatus.FAILED.value
        self.error_message = error
        self.response_payload = response
        self.retry_count += 1
        self.completed_at = utc_now()

    def mark_skipped(self, reason: str = "No changes detected"):
        """Mark this sync as skipped (idempotency check)."""
        self.status = SyncStatus.SKIPPED.value
        self.error_message = reason
        self.completed_at = utc_now()
