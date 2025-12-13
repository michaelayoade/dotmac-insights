from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Numeric, Date, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.expense import Expense


# ============= TASK STATUS =============
class TaskStatus(enum.Enum):
    OPEN = "open"
    WORKING = "working"
    PENDING_REVIEW = "pending_review"
    OVERDUE = "overdue"
    TEMPLATE = "template"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ============= TASK PRIORITY =============
class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ============= TASK =============
class Task(Base):
    """Tasks from ERPNext - work items linked to projects.

    Tasks represent individual work items that can be assigned to users,
    tracked for progress, and linked to projects and expenses.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    erpnext_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    # Basic Info
    subject: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Project link
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    erpnext_project: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Issue/Ticket link (ERPNext Issue doctype)
    issue: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Type and categorization
    task_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status and Priority
    status: Mapped[TaskStatus] = mapped_column(default=TaskStatus.OPEN, index=True)
    priority: Mapped[TaskPriority] = mapped_column(default=TaskPriority.MEDIUM, index=True)

    # Assignment
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    completed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Progress tracking
    progress: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))  # 0-100%
    expected_time: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))  # hours
    actual_time: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))  # hours

    # Dates
    exp_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    exp_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    act_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    act_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Review
    review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    closing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Hierarchy (parent task for sub-tasks)
    parent_task: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    parent_task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True, index=True)
    is_group: Mapped[bool] = mapped_column(default=False)
    is_template: Mapped[bool] = mapped_column(default=False)

    # Company
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Costing
    total_costing_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    total_billing_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    total_expense_claim: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))

    # Template
    template_task: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Workflow
    docstatus: Mapped[int] = mapped_column(default=0)

    # Lft/Rgt for nested set (hierarchy)
    lft: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rgt: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project: Mapped[Optional["Project"]] = relationship(back_populates="tasks")
    parent: Mapped[Optional["Task"]] = relationship(
        "Task", remote_side="Task.id", back_populates="sub_tasks", foreign_keys=[parent_task_id]
    )
    sub_tasks: Mapped[List["Task"]] = relationship(
        "Task", back_populates="parent", foreign_keys=[parent_task_id]
    )
    depends_on: Mapped[List["TaskDependency"]] = relationship(
        back_populates="task", cascade="all, delete-orphan",
        foreign_keys="TaskDependency.task_id"
    )
    dependent_tasks: Mapped[List["TaskDependency"]] = relationship(
        back_populates="dependent_task",
        foreign_keys="TaskDependency.dependent_task_id"
    )
    expenses: Mapped[List["Expense"]] = relationship(back_populates="task")

    def __repr__(self) -> str:
        return f"<Task {self.subject} ({self.status.value})>"

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.exp_end_date and self.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return date.today() > self.exp_end_date
        return False

    @property
    def time_variance(self) -> Decimal:
        """Calculate time variance (actual - expected)."""
        return self.actual_time - self.expected_time


# ============= TASK DEPENDENCY (Child Table) =============
class TaskDependency(Base):
    """Task dependencies - tracks which tasks depend on other tasks.

    This is the 'depends_on' child table from ERPNext Task doctype.
    """

    __tablename__ = "task_dependencies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # The task that has the dependency
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # The task it depends on
    dependent_task_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    dependent_task_erpnext: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Subject of dependent task (for display when FK not resolved)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Project (inherited from parent task usually)
    project: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Row ordering
    idx: Mapped[int] = mapped_column(default=0)

    # ERPNext child row name
    erpnext_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    task: Mapped["Task"] = relationship(
        back_populates="depends_on", foreign_keys=[task_id]
    )
    dependent_task: Mapped[Optional["Task"]] = relationship(
        back_populates="dependent_tasks", foreign_keys=[dependent_task_id]
    )

    def __repr__(self) -> str:
        return f"<TaskDependency task={self.task_id} depends_on={self.dependent_task_erpnext}>"
