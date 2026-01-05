"""
User Activity Log model.

Tracks high-level user actions (auth, approvals, settings, etc.).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ActivityLog(Base):
    """Immutable activity log for user actions."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Action name (e.g., login, settings.update, approval.approve)",
    )

    entity_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Domain/entity type (e.g., settings, approval)",
    )
    entity_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Domain entity identifier",
    )

    summary: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Short human-readable summary",
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Structured metadata for the action",
    )

    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    user_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Denormalized for query without join",
    )

    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_activity_log_entity", "entity_type", "entity_id"),
        Index("ix_activity_log_action_created", "action", "created_at"),
        Index("ix_activity_log_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ActivityLog {self.action} {self.entity_type}:{self.entity_id}>"
