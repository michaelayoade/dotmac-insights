from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import String, Text, Enum, ForeignKey, Index, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now


class CleanupIssueType(enum.Enum):
    """Types of data quality issues that can be detected."""
    DUPLICATE = "duplicate"                 # Duplicate records
    INVALID_FORMAT = "invalid_format"       # Bad phone/email/etc format
    MISSING_REQUIRED = "missing_required"   # Null required fields
    INVALID_VALUE = "invalid_value"         # Value not in allowed set
    ORPHANED = "orphaned"                   # FK points to deleted record
    INCONSISTENT = "inconsistent"           # Conflicting data across fields
    STALE = "stale"                         # Old data needing refresh


class CleanupActionType(enum.Enum):
    """Types of cleanup actions that can be performed."""
    NORMALIZE = "normalize"                 # Apply formatting rules
    MERGE = "merge"                         # Merge duplicate records
    DELETE = "delete"                       # Remove records
    SET_DEFAULT = "set_default"             # Fill missing with default
    SET_NULL = "set_null"                   # Clear invalid values
    LINK = "link"                           # Fix orphaned FKs
    CUSTOM = "custom"                       # User-defined transformation


class IssueSeverity(enum.Enum):
    """Severity levels for cleanup issues."""
    CRITICAL = "critical"                   # Breaks functionality
    HIGH = "high"                           # Causes errors
    MEDIUM = "medium"                       # Data quality issue
    LOW = "low"                             # Cosmetic/minor


class IssueStatus(enum.Enum):
    """Status of a cleanup issue."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class CleanupScanStatus(enum.Enum):
    """Status of a cleanup scan."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CleanupJobStatus(enum.Enum):
    """Status of a cleanup job."""
    PENDING = "pending"
    PREVIEWING = "previewing"
    PREVIEW_READY = "preview_ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class CleanupEntityType(enum.Enum):
    """Entity types supported for cleanup operations."""
    CUSTOMER = "customer"
    CONTACT = "contact"
    SUBSCRIPTION = "subscription"
    SUPPLIER = "supplier"
    EMPLOYEE = "employee"
    INVOICE = "invoice"
    PAYMENT = "payment"


class CleanupRule(Base):
    """Reusable cleanup configuration saved by users."""

    __tablename__ = "cleanup_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Rule identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity_type: Mapped[CleanupEntityType] = mapped_column(
        Enum(CleanupEntityType, values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True
    )

    # Detection criteria
    issue_type: Mapped[CleanupIssueType] = mapped_column(
        Enum(CleanupIssueType, values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True
    )
    detection_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Action configuration
    action_type: Mapped[CleanupActionType] = mapped_column(
        Enum(CleanupActionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    action_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Metadata
    is_system: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    # Relationships
    jobs: Mapped[list["CleanupJob"]] = relationship(
        "CleanupJob",
        back_populates="rule",
        foreign_keys="CleanupJob.rule_id"
    )

    def __repr__(self) -> str:
        return f"<CleanupRule {self.id}: {self.name}>"


class CleanupScan(Base):
    """Background scan job for detecting data quality issues."""

    __tablename__ = "cleanup_scans"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Scan scope
    entity_types: Mapped[list] = mapped_column(JSON, nullable=False)  # List of entity types
    issue_types: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # null = all types

    # Status tracking
    status: Mapped[CleanupScanStatus] = mapped_column(
        Enum(CleanupScanStatus, values_callable=lambda x: [e.value for e in x]),
        default=CleanupScanStatus.PENDING,
        nullable=False,
        index=True
    )
    progress_pct: Mapped[int] = mapped_column(default=0)
    current_step: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Results
    issues_found: Mapped[int] = mapped_column(default=0)
    records_scanned: Mapped[int] = mapped_column(default=0)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Audit
    started_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    issues: Mapped[list["CleanupIssue"]] = relationship(
        "CleanupIssue",
        back_populates="scan",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CleanupScan {self.id}: {self.status.value}>"

    @property
    def is_running(self) -> bool:
        return self.status == CleanupScanStatus.RUNNING

    def start(self) -> None:
        """Mark scan as started."""
        self.status = CleanupScanStatus.RUNNING
        self.started_at = utc_now()

    def complete(self, issues_found: int, records_scanned: int, duration: float) -> None:
        """Mark scan as completed."""
        self.status = CleanupScanStatus.COMPLETED
        self.issues_found = issues_found
        self.records_scanned = records_scanned
        self.duration_seconds = duration
        self.progress_pct = 100
        self.completed_at = utc_now()

    def fail(self, error_message: str) -> None:
        """Mark scan as failed."""
        self.status = CleanupScanStatus.FAILED
        self.error_message = error_message
        self.completed_at = utc_now()


class CleanupIssue(Base):
    """Detected data quality issue."""

    __tablename__ = "cleanup_issues"

    __table_args__ = (
        Index("ix_cleanup_issues_scan_status", "scan_id", "status"),
        Index("ix_cleanup_issues_entity_field", "entity_type", "field_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Scan reference
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("cleanup_scans.id"), nullable=False, index=True
    )

    # Issue classification
    issue_type: Mapped[CleanupIssueType] = mapped_column(
        Enum(CleanupIssueType, values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True
    )
    severity: Mapped[IssueSeverity] = mapped_column(
        Enum(IssueSeverity, values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True
    )
    entity_type: Mapped[CleanupEntityType] = mapped_column(
        Enum(CleanupEntityType, values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True
    )
    field_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Issue description
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Affected records
    record_ids: Mapped[list] = mapped_column(JSON, nullable=False)  # List of affected PKs
    record_count: Mapped[int] = mapped_column(nullable=False)
    sample_values: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Sample bad values

    # Resolution
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, values_callable=lambda x: [e.value for e in x]),
        default=IssueStatus.OPEN,
        nullable=False,
        index=True
    )
    resolution_job_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cleanup_jobs.id"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    # Relationships
    scan: Mapped["CleanupScan"] = relationship("CleanupScan", back_populates="issues")
    resolution_job: Mapped[Optional["CleanupJob"]] = relationship(
        "CleanupJob",
        back_populates="resolved_issues",
        foreign_keys=[resolution_job_id]
    )

    def __repr__(self) -> str:
        return f"<CleanupIssue {self.id}: {self.issue_type.value} ({self.record_count} records)>"

    def resolve(self, job_id: int, user_id: Optional[int] = None) -> None:
        """Mark issue as resolved."""
        self.status = IssueStatus.RESOLVED
        self.resolution_job_id = job_id
        self.resolved_at = utc_now()
        self.resolved_by_id = user_id

    def ignore(self) -> None:
        """Mark issue as ignored."""
        self.status = IssueStatus.IGNORED

    def reopen(self) -> None:
        """Reopen a resolved or ignored issue."""
        self.status = IssueStatus.OPEN
        self.resolution_job_id = None
        self.resolved_at = None
        self.resolved_by_id = None


class CleanupJob(Base):
    """Execution of cleanup operations."""

    __tablename__ = "cleanup_jobs"

    __table_args__ = (
        Index("ix_cleanup_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Job identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cleanup_rules.id"), nullable=True, index=True
    )

    # Scope
    entity_type: Mapped[CleanupEntityType] = mapped_column(
        Enum(CleanupEntityType, values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True
    )
    issue_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Issues being resolved
    record_ids: Mapped[list] = mapped_column(JSON, nullable=False)  # Specific records to clean

    # Execution configuration
    action_type: Mapped[CleanupActionType] = mapped_column(
        Enum(CleanupActionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    action_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Status tracking
    status: Mapped[CleanupJobStatus] = mapped_column(
        Enum(CleanupJobStatus, values_callable=lambda x: [e.value for e in x]),
        default=CleanupJobStatus.PENDING,
        nullable=False,
        index=True
    )

    # Results
    records_processed: Mapped[int] = mapped_column(default=0)
    records_changed: Mapped[int] = mapped_column(default=0)
    records_failed: Mapped[int] = mapped_column(default=0)
    changes_log: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Before/after for each

    # Preview data
    preview_data: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Rollback support
    is_rollbackable: Mapped[bool] = mapped_column(default=True)
    rollback_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    rolled_back_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    rule: Mapped[Optional["CleanupRule"]] = relationship(
        "CleanupRule",
        back_populates="jobs",
        foreign_keys=[rule_id]
    )
    resolved_issues: Mapped[list["CleanupIssue"]] = relationship(
        "CleanupIssue",
        back_populates="resolution_job",
        foreign_keys="CleanupIssue.resolution_job_id"
    )

    def __repr__(self) -> str:
        return f"<CleanupJob {self.id}: {self.name} ({self.status.value})>"

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        total = len(self.record_ids) if self.record_ids else 0
        if total == 0:
            return 0.0
        return round((self.records_processed / total) * 100, 2)

    def start_preview(self) -> None:
        """Mark job as previewing."""
        self.status = CleanupJobStatus.PREVIEWING
        self.started_at = utc_now()

    def complete_preview(self, preview_data: list) -> None:
        """Mark preview as ready."""
        self.status = CleanupJobStatus.PREVIEW_READY
        self.preview_data = preview_data

    def start_execution(self) -> None:
        """Mark job as executing."""
        self.status = CleanupJobStatus.EXECUTING
        self.started_at = utc_now()

    def complete(self, records_changed: int, changes_log: list, rollback_data: dict) -> None:
        """Mark job as completed."""
        self.status = CleanupJobStatus.COMPLETED
        self.records_changed = records_changed
        self.changes_log = changes_log
        self.rollback_data = rollback_data
        self.completed_at = utc_now()

    def fail(self, error_message: str) -> None:
        """Mark job as failed."""
        self.status = CleanupJobStatus.FAILED
        self.error_message = error_message
        self.completed_at = utc_now()

    def rollback(self, user_id: Optional[int] = None) -> None:
        """Mark job as rolled back."""
        self.status = CleanupJobStatus.ROLLED_BACK
        self.rolled_back_at = utc_now()
        self.rolled_back_by_id = user_id
