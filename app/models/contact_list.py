"""
Contact List Model

Allows users to create custom filtered lists of contacts.
Lists can be shared with team members or kept private.
"""
from __future__ import annotations

from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from app.utils.datetime_utils import utc_now
from typing import Optional, TYPE_CHECKING
from app.database import Base

if TYPE_CHECKING:
    from app.models.auth import User


class ContactList(Base):
    """
    Custom contact list with saved filters.

    Users can create lists with specific filter criteria to segment contacts.
    Lists can be shared with the team or kept private.
    """
    __tablename__ = "contact_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ownership and sharing
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Filter criteria stored as JSON
    # Example: {"contact_type": "customer", "category": "business", "territory": "Lagos", "tag": "vip"}
    filters: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Display settings
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color like #3B82F6
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Icon name
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="contact_lists")

    __table_args__ = (
        Index("ix_contact_lists_owner_id", "owner_id"),
        Index("ix_contact_lists_is_shared", "is_shared"),
        Index("ix_contact_lists_is_favorite", "is_favorite"),
    )

    def __repr__(self) -> str:
        return f"<ContactList(id={self.id}, name='{self.name}', owner_id={self.owner_id})>"
