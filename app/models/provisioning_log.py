"""
Provisioning Log Model

Tracks all provisioning operations to MikroTik routers.
Provides audit trail and debugging information.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.subscription import Subscription
    from app.models.router import Router


class ProvisioningAction(enum.Enum):
    """Types of provisioning actions."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    DISCONNECT = "disconnect"
    SUSPEND = "suspend"
    UNSUSPEND = "unsuspend"


class ProvisioningStatus(enum.Enum):
    """Status of provisioning operation."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class ProvisioningLog(Base):
    """
    Log of provisioning operations.

    Records every attempt to provision, update, or deprovision
    a subscription on a MikroTik router.
    """

    __tablename__ = "provisioning_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # References
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id"),
        nullable=False,
        index=True,
    )
    router_id: Mapped[int] = mapped_column(
        ForeignKey("routers.id"),
        nullable=False,
        index=True,
    )

    # Operation details
    action: Mapped[ProvisioningAction] = mapped_column(
        Enum(ProvisioningAction),
        nullable=False,
        index=True,
    )
    access_method: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[ProvisioningStatus] = mapped_column(
        Enum(ProvisioningStatus),
        default=ProvisioningStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Request/Response data
    request_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Timing
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Trigger source
    triggered_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    subscription: Mapped[Subscription] = relationship(backref="provisioning_logs")
    router: Mapped[Router] = relationship(backref="provisioning_logs")

    def __repr__(self) -> str:
        return (
            f"<ProvisioningLog {self.id} "
            f"sub={self.subscription_id} "
            f"action={self.action.value} "
            f"status={self.status.value}>"
        )

    def mark_success(self, response_data: Optional[str] = None) -> None:
        """Mark this log entry as successful."""
        self.status = ProvisioningStatus.SUCCESS
        self.completed_at = datetime.utcnow()
        if response_data:
            self.response_data = response_data
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)

    def mark_failed(
        self,
        error_message: str,
        error_type: Optional[str] = None,
    ) -> None:
        """Mark this log entry as failed."""
        self.status = ProvisioningStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message[:1000] if error_message else None
        self.error_type = error_type
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)

    def mark_retrying(self) -> None:
        """Mark this log entry as retrying."""
        self.status = ProvisioningStatus.RETRYING
        self.retry_count += 1

    @property
    def can_retry(self) -> bool:
        """Check if this operation can be retried."""
        return (
            self.status == ProvisioningStatus.FAILED
            and self.retry_count < self.max_retries
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get duration in seconds."""
        if self.duration_ms:
            return self.duration_ms / 1000
        return None
