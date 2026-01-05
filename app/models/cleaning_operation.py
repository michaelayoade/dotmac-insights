"""CleaningOperation model for tracking data cleaning operations.

Stores operation history with full snapshots for rollback support.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, Any, Dict, List

from sqlalchemy import String, Text, Enum, ForeignKey, Index, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now


class CleaningOperationType(enum.Enum):
    """Types of cleaning operations."""
    BULK_UPDATE = "bulk_update"     # Update field values
    NORMALIZE = "normalize"         # Phone/email/address normalization
    MERGE = "merge"                 # Merge duplicate records
    LINK = "link"                   # Link orphan records


class CleaningOperationStatus(enum.Enum):
    """Status of a cleaning operation."""
    PENDING = "pending"             # Created but not started
    EXECUTING = "executing"         # Currently running
    COMPLETED = "completed"         # Successfully finished
    FAILED = "failed"               # Failed during execution
    ROLLED_BACK = "rolled_back"     # Successfully rolled back


class CleaningOperation(Base):
    """Record of a data cleaning operation for audit and rollback.

    Each operation stores:
    - What was changed (operation type, table, filters)
    - Before/after snapshots for each affected record
    - Who performed it and when
    - Whether it can be/has been rolled back
    """

    __tablename__ = "cleaning_operations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Unique operation identifier (UUID)
    operation_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, nullable=False
    )

    # Operation type
    operation_type: Mapped[CleaningOperationType] = mapped_column(
        Enum(CleaningOperationType, values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True
    )

    # Status tracking
    status: Mapped[CleaningOperationStatus] = mapped_column(
        Enum(CleaningOperationStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=CleaningOperationStatus.PENDING, index=True
    )

    # Target table
    table_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Execution details
    records_affected: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)

    # Operation configuration (filters, updates planned, etc.)
    operation_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, default=dict, nullable=True
    )

    # Changes log: list of {record_id, before, after, changed_fields}
    changes_log: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB, default=list, nullable=True
    )

    # Rollback data: {record_id: {full snapshot before change}}
    rollback_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, default=dict, nullable=True
    )

    # Errors: list of {record_id, error, field}
    errors: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB, default=list, nullable=True
    )

    # Summary metadata (operation-specific info for display)
    summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, default=dict, nullable=True
    )

    # Rollback state
    is_rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    rolled_back_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # User who created the operation
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_cleaning_ops_status_created", "status", "created_at"),
        Index("ix_cleaning_ops_table_created", "table_name", "created_at"),
        Index("ix_cleaning_ops_type_status", "operation_type", "status"),
    )

    # ==========================================================================
    # State transition methods
    # ==========================================================================

    def start(self) -> None:
        """Mark operation as executing."""
        self.status = CleaningOperationStatus.EXECUTING
        self.started_at = utc_now()

    def complete(
        self,
        records_affected: int,
        records_failed: int,
        changes_log: List[Dict[str, Any]],
        rollback_data: Dict[str, Any],
        errors: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Mark operation as completed."""
        self.status = CleaningOperationStatus.COMPLETED
        self.completed_at = utc_now()
        self.records_affected = records_affected
        self.records_failed = records_failed
        self.changes_log = changes_log
        self.rollback_data = rollback_data
        self.errors = errors or []

    def fail(self, error_message: str) -> None:
        """Mark operation as failed."""
        self.status = CleaningOperationStatus.FAILED
        self.completed_at = utc_now()
        self.summary = {**(self.summary or {}), "error": error_message}

    def rollback(self, user_id: int) -> None:
        """Mark operation as rolled back."""
        self.is_rolled_back = True
        self.rolled_back_at = utc_now()
        self.rolled_back_by_id = user_id
        self.status = CleaningOperationStatus.ROLLED_BACK

    # ==========================================================================
    # Helper properties
    # ==========================================================================

    @property
    def is_rollbackable(self) -> bool:
        """Check if operation can be rolled back."""
        return (
            self.status == CleaningOperationStatus.COMPLETED
            and not self.is_rolled_back
            and bool(self.rollback_data)
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get operation duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
