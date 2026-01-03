"""Notification and webhook models."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Text, ForeignKey, Enum, Index, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationChannel(enum.Enum):
    """Supported notification channels."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    IN_APP = "in_app"
    SMS = "sms"
    SLACK = "slack"


class NotificationEventType(enum.Enum):
    """Types of events that can trigger notifications."""
    # Approval workflow events
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_ESCALATED = "approval_escalated"

    # Invoice events
    INVOICE_CREATED = "invoice_created"
    INVOICE_OVERDUE = "invoice_overdue"
    INVOICE_PAID = "invoice_paid"
    INVOICE_WRITTEN_OFF = "invoice_written_off"

    # Dunning events
    DUNNING_SENT = "dunning_sent"
    DUNNING_ESCALATED = "dunning_escalated"

    # Payment events
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"

    # Period events
    PERIOD_CLOSING = "period_closing"
    PERIOD_CLOSED = "period_closed"

    # Tax events
    TAX_DUE_REMINDER = "tax_due_reminder"
    TAX_OVERDUE = "tax_overdue"

    # Credit events
    CREDIT_LIMIT_WARNING = "credit_limit_warning"
    CREDIT_HOLD_APPLIED = "credit_hold_applied"

    # Inventory events
    STOCK_LOW = "stock_low"
    STOCK_REORDER = "stock_reorder"

    # Reconciliation events
    RECONCILIATION_COMPLETE = "reconciliation_complete"
    RECONCILIATION_DISCREPANCY = "reconciliation_discrepancy"

    # Performance management events
    PERF_PERIOD_STARTED = "perf_period_started"  # Evaluation period activated
    PERF_SCORECARD_GENERATED = "perf_scorecard_generated"  # Scorecard created for employee
    PERF_SCORECARD_COMPUTED = "perf_scorecard_computed"  # Metrics calculated
    PERF_REVIEW_REQUESTED = "perf_review_requested"  # Submitted for manager review
    PERF_SCORECARD_APPROVED = "perf_scorecard_approved"  # Manager approved
    PERF_SCORECARD_REJECTED = "perf_scorecard_rejected"  # Manager sent back for revision
    PERF_SCORECARD_FINALIZED = "perf_scorecard_finalized"  # Final rating assigned
    PERF_SCORE_OVERRIDDEN = "perf_score_overridden"  # Score manually adjusted
    PERF_REVIEW_REMINDER = "perf_review_reminder"  # Reminder to complete review
    PERF_PERIOD_CLOSING = "perf_period_closing"  # Period ending soon
    PERF_WEEKLY_SUMMARY = "perf_weekly_summary"  # Weekly manager summary
    PERF_RATING_PUBLISHED = "perf_rating_published"  # Rating visible to employee

    # Project management events
    PROJECT_CREATED = "project_created"  # New project created
    PROJECT_STATUS_CHANGED = "project_status_changed"  # Status updated
    PROJECT_ASSIGNED = "project_assigned"  # User assigned to project
    PROJECT_OVERDUE = "project_overdue"  # Project past expected end date
    PROJECT_COMPLETED = "project_completed"  # Project marked complete
    PROJECT_APPROVAL_REQUESTED = "project_approval_requested"  # Submitted for approval
    PROJECT_APPROVED = "project_approved"  # Project approved
    PROJECT_REJECTED = "project_rejected"  # Project rejected

    # Task events
    TASK_ASSIGNED = "task_assigned"  # Task assigned to user
    TASK_COMPLETED = "task_completed"  # Task marked complete
    TASK_OVERDUE = "task_overdue"  # Task past expected end date
    TASK_COMMENT_ADDED = "task_comment_added"  # New comment on task

    # Milestone events
    MILESTONE_APPROACHING = "milestone_approaching"  # Milestone due soon
    MILESTONE_COMPLETED = "milestone_completed"  # Milestone completed
    MILESTONE_OVERDUE = "milestone_overdue"  # Milestone past due date

    # Generic
    CUSTOM = "custom"


class NotificationStatus(enum.Enum):
    """Status of a notification."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"


class WebhookConfig(Base):
    """Webhook endpoint configuration."""

    __tablename__ = "webhook_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Endpoint
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="POST")  # POST, PUT

    # Authentication
    auth_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # none, basic, bearer, api_key
    auth_header: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Header name for API key
    auth_value_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Encrypted token/key

    # Headers
    custom_headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Events to subscribe to
    event_types: Mapped[List[str]] = mapped_column(JSON, default=list)  # List of NotificationEventType values

    # Filters (optional)
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # e.g., {"customer_id": [1,2,3]}

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)

    # Retry config
    max_retries: Mapped[int] = mapped_column(default=3)
    retry_delay_seconds: Mapped[int] = mapped_column(default=60)

    # Secret for signature verification
    signing_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Stats
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    success_count: Mapped[int] = mapped_column(default=0)
    failure_count: Mapped[int] = mapped_column(default=0)

    # Ownership
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    deliveries: Mapped[List["WebhookDelivery"]] = relationship(back_populates="webhook", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_webhook_configs_active_events", "is_active", "is_deleted"),
    )

    def __repr__(self) -> str:
        return f"<WebhookConfig {self.name} -> {self.url}>"


class WebhookDelivery(Base):
    """Record of webhook delivery attempts."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhook_configs.id"), nullable=False, index=True)

    # Event info
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False)  # UUID for deduplication

    # Payload
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Delivery status
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus), default=NotificationStatus.PENDING
    )
    attempt_count: Mapped[int] = mapped_column(default=0)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Response info
    response_status_code: Mapped[Optional[int]] = mapped_column(nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationship
    webhook: Mapped["WebhookConfig"] = relationship(back_populates="deliveries")

    __table_args__ = (
        Index("ix_webhook_deliveries_status_retry", "status", "next_retry_at"),
        Index("ix_webhook_deliveries_event", "event_type", "event_id"),
    )

    def __repr__(self) -> str:
        return f"<WebhookDelivery {self.event_type} status={self.status.value}>"


class NotificationPreference(Base):
    """User notification preferences."""

    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Event type
    event_type: Mapped[NotificationEventType] = mapped_column(
        Enum(NotificationEventType), nullable=False
    )

    # Channel preferences
    email_enabled: Mapped[bool] = mapped_column(default=True)
    in_app_enabled: Mapped[bool] = mapped_column(default=True)
    sms_enabled: Mapped[bool] = mapped_column(default=False)
    slack_enabled: Mapped[bool] = mapped_column(default=False)

    # Custom settings
    threshold_amount: Mapped[Optional[Decimal]] = mapped_column(nullable=True)  # Only notify if amount > threshold
    threshold_days: Mapped[Optional[int]] = mapped_column(nullable=True)  # e.g., notify 7 days before due

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_notification_prefs_user_event", "user_id", "event_type", unique=True),
    )

    def __repr__(self) -> str:
        return f"<NotificationPreference user={self.user_id} event={self.event_type.value}>"


class Notification(Base):
    """In-app notification for users."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Target user
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Event info
    event_type: Mapped[NotificationEventType] = mapped_column(
        Enum(NotificationEventType), nullable=False, index=True
    )

    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Icon name/class

    # Link to related entity
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # invoice, payment, etc.
    entity_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    action_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Extra data
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Status
    is_read: Mapped[bool] = mapped_column(default=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Priority
    priority: Mapped[str] = mapped_column(String(20), default="normal")  # low, normal, high, urgent

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "is_read", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification {self.event_type.value} for user={self.user_id}>"


class EmailQueue(Base):
    """Queue for outgoing emails."""

    __tablename__ = "email_queue"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Recipient
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    to_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cc_emails: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    bcc_emails: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Content
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Event reference
    event_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Status
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus), default=NotificationStatus.PENDING, index=True
    )
    attempt_count: Mapped[int] = mapped_column(default=0)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Priority for queue ordering
    priority: Mapped[int] = mapped_column(default=5)  # 1=highest, 10=lowest

    __table_args__ = (
        Index("ix_email_queue_pending", "status", "priority", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EmailQueue {self.to_email} status={self.status.value}>"
