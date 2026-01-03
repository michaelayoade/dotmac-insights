from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from app.database import Base

if TYPE_CHECKING:
    from app.models.employee import Employee


# ============= DEPARTMENT =============
class Department(Base):
    """Departments from ERPNext HR module."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    department_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    parent_department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_group: Mapped[bool] = mapped_column(default=False)

    # Tree structure
    lft: Mapped[Optional[int]] = mapped_column(nullable=True)
    rgt: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Department {self.department_name}>"


# ============= HD TEAM (Helpdesk Team) =============
class HDTeam(Base):
    """Helpdesk teams from ERPNext."""

    __tablename__ = "hd_teams"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    team_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Assignment rules
    assignment_rule: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ignore_restrictions: Mapped[bool] = mapped_column(default=False)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    members: Mapped[List["HDTeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<HDTeam {self.team_name}>"


# ============= HD TEAM MEMBER =============
class HDTeamMember(Base):
    """Helpdesk team members - linking users to teams."""

    __tablename__ = "hd_team_members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Team relationship
    team_id: Mapped[int] = mapped_column(ForeignKey("hd_teams.id"), nullable=False, index=True)

    # User info
    user: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Link to employee (if found)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)

    # Sync metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    team: Mapped["HDTeam"] = relationship(back_populates="members")
    employee: Mapped[Optional["Employee"]] = relationship()

    def __repr__(self) -> str:
        return f"<HDTeamMember {self.user} in team_id={self.team_id}>"


# ============= DESIGNATION =============
class Designation(Base):
    """Job designations/titles from ERPNext."""

    __tablename__ = "designations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    designation_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Designation {self.designation_name}>"


# ============= USER (ERPNext User) =============
class ERPNextUser(Base):
    """ERPNext system users - links employees to system access."""

    __tablename__ = "erpnext_users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Basic info
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    enabled: Mapped[bool] = mapped_column(default=True)
    user_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Link to employee
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee: Mapped[Optional["Employee"]] = relationship()

    def __repr__(self) -> str:
        return f"<ERPNextUser {self.email}>"
