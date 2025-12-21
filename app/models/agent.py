from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Agent(Base):
    """Unified agent identity across support/sales/projects."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)

    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Capability & routing metadata
    domains: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # e.g., {"support": true, "sales": true}
    skills: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)   # e.g., {"network": 3, "billing": 2}
    channel_caps: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # e.g., {"email": true, "whatsapp": true}
    routing_weight: Mapped[int] = mapped_column(Integer, default=1)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    team_memberships: Mapped[List["TeamMember"]] = relationship(back_populates="agent", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Agent {self.display_name or self.email or self.id}>"


class Team(Base):
    """Teams that group agents, domain-aware."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    domain: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)  # support|sales|projects|mixed
    assignment_rule: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    members: Mapped[List["TeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Team {self.name}>"


class TeamMember(Base):
    """Membership linking agents to teams."""

    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)

    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # lead/member
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    team: Mapped["Team"] = relationship(back_populates="members")
    agent: Mapped["Agent"] = relationship(back_populates="team_memberships")

    def __repr__(self) -> str:
        return f"<TeamMember team={self.team_id} agent={self.agent_id}>"
