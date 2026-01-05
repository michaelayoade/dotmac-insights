from __future__ import annotations

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Integer, Boolean, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.party import Party


class Team(Base):
    """Teams that group agents, domain-aware."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    domain: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)  # support|sales|projects|mixed
    assignment_rule: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Chatwoot sync
    chatwoot_team_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True, index=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    members: Mapped[List["TeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Team {self.name}>"


class TeamMember(Base):
    """Membership linking parties (support agents) to teams.

    After Agent → Party unification, team membership is now based on Party.
    A Party must have PartyRole(role="support_agent") to be a valid team member.
    """

    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # lead/member
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    team: Mapped["Team"] = relationship(back_populates="members")
    party: Mapped["Party"] = relationship(foreign_keys=[party_id])

    def __repr__(self) -> str:
        return f"<TeamMember team={self.team_id} party={self.party_id}>"
