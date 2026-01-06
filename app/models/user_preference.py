"""User preferences model for launcher favorites and UI settings.

This module defines the database model for user preferences, including:
- Favorite modules for the launcher
- Extended preferences (theme, defaults, etc.)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.auth import User


class UserPreference(Base):
    """User preferences including launcher favorites and UI settings.

    This model stores per-user preferences as JSONB for flexibility.
    Each user has at most one preference record (one-to-one with User).
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Link to user (one-to-one, cascade delete)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Launcher favorites - list of module IDs
    # e.g., ["customer", "finance", "operations"]
    favorite_modules: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        server_default="'[]'::jsonb",
    )

    # Extended preferences (flexible JSONB for future settings)
    # e.g., {"theme": "dark", "default_module": "crm", "sidebar_collapsed": false}
    preferences: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        server_default="'{}'::jsonb",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationship back to User
    user: Mapped["User"] = relationship(back_populates="preference")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )

    def __repr__(self) -> str:
        return f"<UserPreference user_id={self.user_id}>"

    def get_preference(self, key: str, default: Optional[any] = None) -> any:
        """Get a specific preference value."""
        return self.preferences.get(key, default) if self.preferences else default

    def set_preference(self, key: str, value: any) -> None:
        """Set a specific preference value."""
        if self.preferences is None:
            self.preferences = {}
        self.preferences[key] = value

    def is_favorite(self, module_id: str) -> bool:
        """Check if a module is in favorites."""
        return module_id in (self.favorite_modules or [])

    def add_favorite(self, module_id: str) -> None:
        """Add a module to favorites."""
        if self.favorite_modules is None:
            self.favorite_modules = []
        if module_id not in self.favorite_modules:
            self.favorite_modules = [*self.favorite_modules, module_id]

    def remove_favorite(self, module_id: str) -> None:
        """Remove a module from favorites."""
        if self.favorite_modules and module_id in self.favorite_modules:
            self.favorite_modules = [m for m in self.favorite_modules if m != module_id]
