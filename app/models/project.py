from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.employee import Employee
    from app.models.expense import Expense
    from app.models.ticket import Ticket
    from app.models.task import Task


class ProjectStatus(enum.Enum):
    OPEN = "open"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class ProjectPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProjectType(enum.Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    SERVICE = "service"


class Project(Base):
    """Project records from ERPNext."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External ID
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Basic info
    project_name: Mapped[str] = mapped_column(String(500), nullable=False)
    project_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.OPEN, index=True)
    priority: Mapped[ProjectPriority] = mapped_column(Enum(ProjectPriority), default=ProjectPriority.MEDIUM)

    # Organization
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cost_center: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # FK Relationships
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    project_manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)

    # ERPNext references (for linking)
    erpnext_customer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    erpnext_sales_order: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Progress
    percent_complete: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    percent_complete_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[str] = mapped_column(String(10), default="Yes")

    # Dates
    expected_start_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    expected_end_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    actual_start_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    actual_end_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Time tracking
    actual_time: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_consumed_material_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Costing - Estimated
    estimated_costing: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Costing - Actual
    total_costing_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_expense_claim: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_purchase_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Revenue
    total_sales_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_billable_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_billed_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Margin
    gross_margin: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    per_gross_margin: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    # Billing
    collect_progress: Mapped[bool] = mapped_column(default=False)
    frequency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    from_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    to_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Message
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship(back_populates="projects")
    project_manager: Mapped[Optional["Employee"]] = relationship(back_populates="managed_projects")
    expenses: Mapped[List["Expense"]] = relationship(back_populates="project")
    tickets: Mapped[List["Ticket"]] = relationship(back_populates="project")
    tasks: Mapped[List["Task"]] = relationship(back_populates="project")
    users: Mapped[List["ProjectUser"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project {self.project_name} - {self.status.value}>"

    @property
    def profit_margin_percent(self) -> Decimal:
        """Calculate profit margin as percentage."""
        if self.total_billed_amount > 0:
            return (self.gross_margin / self.total_billed_amount) * 100
        return Decimal("0")

    @property
    def is_overdue(self) -> bool:
        """Check if project is overdue."""
        if self.expected_end_date and self.status == ProjectStatus.OPEN:
            return utc_now() > self.expected_end_date
        return False


class ProjectUser(Base):
    """Project team members (child table from ERPNext)."""

    __tablename__ = "project_users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    view_attachments: Mapped[Optional[bool]] = mapped_column(nullable=True)
    welcome_email_sent: Mapped[Optional[bool]] = mapped_column(nullable=True)
    idx: Mapped[Optional[int]] = mapped_column(nullable=True)
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationship
    project: Mapped["Project"] = relationship(back_populates="users")
