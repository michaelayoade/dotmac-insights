"""
Webhook Event Model

Tracks webhook events for idempotency and audit.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Index, JSON, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WebhookEvent(Base):
    """
    Webhook event tracking for idempotency.

    Prevents duplicate processing of webhook events by tracking
    which events have been received and processed.
    """

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Provider identification
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_event_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    # Event details
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Processing status
    processed: Mapped[bool] = mapped_column(default=False, index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Error tracking
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)
    last_retry_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Related entity (if applicable)
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # gateway_transaction, transfer, subscription
    entity_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # IP address of webhook sender
    source_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_event_id",
            name="uq_webhook_event_provider_event"
        ),
        Index("ix_webhook_event_provider_type", "provider", "event_type"),
        Index("ix_webhook_event_processed", "processed", "received_at"),
    )

    def __repr__(self) -> str:
        return f"<WebhookEvent {self.provider} {self.event_type} {self.provider_event_id}>"

    @property
    def is_processed(self) -> bool:
        """Check if event was processed."""
        return self.processed

    @property
    def has_error(self) -> bool:
        """Check if event processing had an error."""
        return self.error is not None
