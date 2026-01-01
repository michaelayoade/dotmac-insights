"""Ticket tags and custom fields models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import String, Text, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomFieldType(str, Enum):
    """Types of custom fields."""
    TEXT = "text"
    NUMBER = "number"
    DROPDOWN = "dropdown"
    MULTI_SELECT = "multi_select"
    DATE = "date"
    DATETIME = "datetime"
    CHECKBOX = "checkbox"
    URL = "url"
    EMAIL = "email"


class TicketTag(Base):
    """Tag that can be applied to tickets.

    Tags help with categorization, filtering, and automation.
    """

    __tablename__ = "ticket_tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Hex color like #FF5733
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Usage tracking
    usage_count: Mapped[int] = mapped_column(Integer, default=0)

    # Flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TicketTag {self.name}>"


class TicketCustomField(Base):
    """Definition of a custom field for tickets.

    Custom fields allow organizations to capture additional
    ticket metadata beyond standard fields.

    Options format (for dropdown/multi_select):
    [
        {"value": "option1", "label": "Option 1"},
        {"value": "option2", "label": "Option 2"}
    ]
    """

    __tablename__ = "ticket_custom_fields"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    field_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Field type
    field_type: Mapped[str] = mapped_column(String(50), default=CustomFieldType.TEXT.value)

    # Options for dropdown/multi_select types
    options: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Default value
    default_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Validation
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    min_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    regex_pattern: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Display
    display_order: Mapped[int] = mapped_column(Integer, default=100)
    show_in_list: Mapped[bool] = mapped_column(Boolean, default=False)  # Show in ticket list view
    show_in_create: Mapped[bool] = mapped_column(Boolean, default=True)  # Show in create form

    # Flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TicketCustomField {self.field_key} ({self.field_type})>"
