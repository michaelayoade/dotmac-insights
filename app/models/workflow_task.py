"""Unified workflow task model for cross-module task management."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base

if TYPE_CHECKING:
    from app.models.auth import User
    from app.models.employee import Employee


class WorkflowTaskStatus(enum.Enum):
    """Status of a workflow task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class WorkflowTaskPriority(enum.Enum):
    """Priority levels for workflow tasks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class WorkflowTaskModule(enum.Enum):
    """Module that owns the task source."""
    ACCOUNTING = "accounting"
    SUPPORT = "support"
    EXPENSES = "expenses"
    PERFORMANCE = "performance"
    INBOX = "inbox"
    HR = "hr"
    PROJECTS = "projects"
    CRM = "crm"


class WorkflowTaskSourceType(enum.Enum):
    """Type of source entity that created the task."""
    APPROVAL = "approval"
    TICKET = "ticket"
    EXPENSE_CLAIM = "expense_claim"
    CASH_ADVANCE = "cash_advance"
    SCORECARD = "scorecard"
    CONVERSATION = "conversation"
    PROJECT_TASK = "project_task"
    LEAD = "lead"


class WorkflowTask(Base):
    """
    Unified task model aggregating human action items from all modules.

    Tasks are automatically created when:
    - Approval workflows submit documents for approval
    - Support tickets are assigned to agents
    - Expense claims/cash advances are submitted
    - Performance scorecards enter review phase
    - Inbox conversations are assigned

    This provides a single "My Tasks" view across the entire system.
    """

    __tablename__ = "workflow_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Polymorphic source reference
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="approval, ticket, expense_claim, cash_advance, scorecard, conversation"
    )
    source_id: Mapped[int] = mapped_column(nullable=False)

    # Task details
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to take action on this task"
    )

    # Assignment
    assignee_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    assignee_employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True
    )
    assignee_team_id: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Reference to teams table"
    )
    assigned_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    assigned_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Priority and timing
    priority: Mapped[str] = mapped_column(
        String(20),
        default="medium",
        comment="low, medium, high, urgent"
    )
    due_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        comment="pending, in_progress, completed, cancelled, expired"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Context
    module: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="accounting, support, expenses, performance, inbox, hr, projects"
    )
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    task_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Additional context data"
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    assignee_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assignee_user_id],
        lazy="joined"
    )
    assignee_employee: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        foreign_keys=[assignee_employee_id],
        lazy="joined"
    )
    assigned_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_by_id],
        lazy="select"
    )
    completed_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[completed_by_id],
        lazy="select"
    )

    __table_args__ = (
        # One task per source per user
        UniqueConstraint(
            "source_type",
            "source_id",
            "assignee_user_id",
            name="uq_workflow_tasks_source_user"
        ),
        # Partial indexes for common queries
        Index(
            "ix_workflow_tasks_assignee_user",
            "assignee_user_id",
            "status",
            "due_at",
            postgresql_where="assignee_user_id IS NOT NULL"
        ),
        Index(
            "ix_workflow_tasks_assignee_employee",
            "assignee_employee_id",
            "status",
            "due_at",
            postgresql_where="assignee_employee_id IS NOT NULL"
        ),
        Index("ix_workflow_tasks_source", "source_type", "source_id"),
        Index("ix_workflow_tasks_module_status", "module", "status"),
        Index(
            "ix_workflow_tasks_due_at",
            "due_at",
            postgresql_where="status = 'pending' AND due_at IS NOT NULL"
        ),
    )

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.due_at is None:
            return False
        if self.status != WorkflowTaskStatus.PENDING.value:
            return False
        return datetime.utcnow() > self.due_at

    @property
    def assignee_display_name(self) -> str:
        """Get display name for assignee."""
        if self.assignee_user:
            return self.assignee_user.display_name or self.assignee_user.email
        if self.assignee_employee:
            return self.assignee_employee.employee_name or str(self.assignee_employee.id)
        return "Unassigned"

    def __repr__(self) -> str:
        return f"<WorkflowTask(id={self.id}, source={self.source_type}:{self.source_id}, status={self.status})>"
