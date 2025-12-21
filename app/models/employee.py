from __future__ import annotations

from sqlalchemy import String, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.utils.datetime_utils import utc_now
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.project import Project
    from app.models.expense import Expense
    from app.models.hr import Department, Designation
    from app.models.expense_management import ExpenseClaim, CashAdvance, CorporateCard
    from app.models.unified_ticket import UnifiedTicket
    from app.models.field_service import (
        ServiceOrder, FieldTeam, FieldTeamMember, TechnicianSkill, ServiceTimeEntry
    )


class EmploymentStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"
    ON_LEAVE = "on_leave"


class Employee(Base):
    """Employee records from ERPNext."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External ID
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    chatwoot_agent_id: Mapped[Optional[int]] = mapped_column(index=True, nullable=True)

    # Basic info
    employee_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Position (text fields for ERPNext values)
    designation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    reports_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Position (FK relationships)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    designation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("designations.id"), nullable=True, index=True)
    reports_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)

    # Employment
    status: Mapped[EmploymentStatus] = mapped_column(Enum(EmploymentStatus), default=EmploymentStatus.ACTIVE, index=True)
    employment_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    date_of_joining: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    date_of_leaving: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Compensation
    salary: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    # Soft delete columns
    is_deleted: Mapped[bool] = mapped_column(default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    deleted_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    tickets: Mapped[List[Ticket]] = relationship(
        back_populates="employee",
        foreign_keys="[Ticket.employee_id]"
    )
    managed_projects: Mapped[List[Project]] = relationship(back_populates="project_manager")
    expenses: Mapped[List[Expense]] = relationship(back_populates="employee")
    expense_claims: Mapped[List["ExpenseClaim"]] = relationship(back_populates="employee")
    cash_advances: Mapped[List["CashAdvance"]] = relationship(back_populates="employee")
    corporate_cards: Mapped[List["CorporateCard"]] = relationship(back_populates="employee")

    # HR Relationships
    department_rel: Mapped[Optional["Department"]] = relationship(foreign_keys=[department_id])
    designation_rel: Mapped[Optional["Designation"]] = relationship(foreign_keys=[designation_id])
    manager: Mapped[Optional["Employee"]] = relationship(
        foreign_keys=[reports_to_id],
        remote_side="Employee.id",
        backref="direct_reports"
    )

    # Ticket assignments (back_populates for Ticket.assigned_employee)
    assigned_tickets: Mapped[List["Ticket"]] = relationship(
        "Ticket",
        back_populates="assigned_employee",
        foreign_keys="[Ticket.assigned_employee_id]"
    )

    # Unified ticket assignments
    assigned_unified_tickets: Mapped[List["UnifiedTicket"]] = relationship(
        "UnifiedTicket",
        back_populates="assigned_to",
        foreign_keys="[UnifiedTicket.assigned_to_id]"
    )
    created_unified_tickets: Mapped[List["UnifiedTicket"]] = relationship(
        "UnifiedTicket",
        back_populates="created_by",
        foreign_keys="[UnifiedTicket.created_by_id]"
    )

    # Field service relationships
    service_orders: Mapped[List["ServiceOrder"]] = relationship(
        "ServiceOrder",
        back_populates="technician",
        foreign_keys="[ServiceOrder.assigned_technician_id]"
    )
    supervised_field_teams: Mapped[List["FieldTeam"]] = relationship(
        "FieldTeam",
        back_populates="supervisor",
        foreign_keys="[FieldTeam.supervisor_id]"
    )
    field_team_memberships: Mapped[List["FieldTeamMember"]] = relationship(
        "FieldTeamMember",
        back_populates="employee",
        foreign_keys="[FieldTeamMember.employee_id]"
    )
    technician_skills: Mapped[List["TechnicianSkill"]] = relationship(
        "TechnicianSkill",
        back_populates="employee",
        foreign_keys="[TechnicianSkill.employee_id]"
    )
    service_time_entries: Mapped[List["ServiceTimeEntry"]] = relationship(
        "ServiceTimeEntry",
        back_populates="employee",
        foreign_keys="[ServiceTimeEntry.employee_id]"
    )

    def __repr__(self) -> str:
        return f"<Employee {self.name} - {self.department}>"
