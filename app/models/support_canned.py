"""Canned responses (macros) for support tickets."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.agent import Agent, Team


class CannedResponseScope(str, Enum):
    """Scope/visibility of a canned response."""
    PERSONAL = "personal"   # Only the creator can use
    TEAM = "team"           # Team members can use
    GLOBAL = "global"       # All agents can use


class CannedResponse(Base):
    """Canned response template for quick ticket replies.

    Supports placeholder variables like {{customer_name}}, {{ticket_id}}.
    Can be scoped to personal, team, or global visibility.
    """

    __tablename__ = "canned_responses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    shortcode: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, nullable=True, index=True
    )  # e.g., /greeting, /thanks

    # Content (supports Markdown and placeholders)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Scope and ownership
    scope: Mapped[str] = mapped_column(
        String(20), default=CannedResponseScope.PERSONAL.value, index=True
    )

    # For TEAM scope - which team
    team_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # For PERSONAL scope - which agent owns it
    agent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Organization
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Usage tracking
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    team: Mapped[Optional["Team"]] = relationship()
    agent: Mapped[Optional["Agent"]] = relationship()

    def __repr__(self) -> str:
        return f"<CannedResponse {self.name} ({self.scope})>"

    def render(self, context: dict) -> str:
        """Render the canned response with context variables.

        Supported placeholders:
        - {{customer_name}}
        - {{ticket_id}}
        - {{ticket_subject}}
        - {{agent_name}}
        - {{company_name}}
        - And any custom keys in context

        Args:
            context: Dict of placeholder values

        Returns:
            Rendered content with placeholders replaced
        """
        result = self.content
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            result = result.replace(placeholder, str(value))
        return result
