"""
General Settings Models

Runtime-configurable application settings with:
- Encrypted storage for secrets (via OpenBao Transit)
- JSON-per-group storage for atomic updates
- Audit logging for all changes
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SettingGroup(Base):
    """
    Application settings stored as encrypted JSON per group.

    Groups: email, payments, webhooks, sms, notifications, branding, localization
    """
    __tablename__ = "setting_groups"

    id: Mapped[int] = mapped_column(primary_key=True)

    group_name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        comment="Setting group identifier (email, payments, etc.)"
    )

    schema_version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False,
        comment="Schema version for migration support"
    )

    data_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="OpenBao Transit encrypted JSON blob"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    # Relationships
    updated_by = relationship("User", foreign_keys=[updated_by_id])


class SettingsAuditLog(Base):
    """
    Audit log for settings changes.

    Stores who changed what and when, with secrets redacted.
    """
    __tablename__ = "settings_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)

    group_name: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="Setting group that was modified"
    )

    action: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Action type: create, update, delete, test"
    )

    # Changes (secrets redacted as ***REDACTED***)
    old_value_redacted: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Previous value with secrets redacted"
    )
    new_value_redacted: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="New value with secrets redacted"
    )

    # Who made the change
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    user_email: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Denormalized for query without join"
    )

    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True,
        comment="Client IP address"
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="Client user agent"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_settings_audit_group_created", "group_name", "created_at"),
    )
