from __future__ import annotations

from sqlalchemy import String, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.project import Project
    from app.models.expense import Expense
    from app.models.hr import Department, Designation


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
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tickets: Mapped[List[Ticket]] = relationship(
        back_populates="employee",
        foreign_keys="[Ticket.employee_id]"
    )
    managed_projects: Mapped[List[Project]] = relationship(back_populates="project_manager")
    expenses: Mapped[List[Expense]] = relationship(back_populates="employee")

    # HR Relationships
    department_rel: Mapped[Optional["Department"]] = relationship(foreign_keys=[department_id])
    designation_rel: Mapped[Optional["Designation"]] = relationship(foreign_keys=[designation_id])
    manager: Mapped[Optional["Employee"]] = relationship(
        foreign_keys=[reports_to_id],
        remote_side="Employee.id",
        backref="direct_reports"
    )

    def __repr__(self) -> str:
        return f"<Employee {self.name} - {self.department}>"
