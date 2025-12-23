from __future__ import annotations

from sqlalchemy import String, Text, ForeignKey, Enum, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum
from app.database import Base, SoftDeleteMixin
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.employee import Employee
    from app.models.expense import Expense
    from app.models.ticket import Ticket
    from app.models.task import Task
    from app.models.auth import User


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


class MilestoneStatus(enum.Enum):
    """Status for project milestones."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class ProjectActivityType(enum.Enum):
    """Activity types for project audit trail."""
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    COMMENT_ADDED = "comment_added"
    ATTACHMENT_ADDED = "attachment_added"
    MILESTONE_COMPLETED = "milestone_completed"
    TASK_COMPLETED = "task_completed"
    APPROVAL_SUBMITTED = "approval_submitted"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"


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
    milestones: Mapped[List["Milestone"]] = relationship(back_populates="project", cascade="all, delete-orphan")

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


class Milestone(SoftDeleteMixin, Base):
    """Project milestones for tracking key deliverables."""

    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[MilestoneStatus] = mapped_column(
        Enum(MilestoneStatus), default=MilestoneStatus.PLANNED, index=True
    )

    # Dates
    planned_start_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    planned_end_date: Mapped[Optional[date]] = mapped_column(nullable=True, index=True)
    actual_start_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    actual_end_date: Mapped[Optional[date]] = mapped_column(nullable=True)

    # Progress
    percent_complete: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))

    # Ordering
    idx: Mapped[int] = mapped_column(default=0)

    # Organization
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="milestones")
    tasks: Mapped[List["Task"]] = relationship(back_populates="milestone")
    created_by: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by_id])

    def __repr__(self) -> str:
        return f"<Milestone {self.name} - {self.status.value}>"

    @property
    def is_overdue(self) -> bool:
        """Check if milestone is overdue."""
        if self.planned_end_date and self.status not in [MilestoneStatus.COMPLETED]:
            return date.today() > self.planned_end_date
        return False


class ProjectComment(Base):
    """Polymorphic comments for Project, Task, Milestone (internal only)."""

    __tablename__ = "project_comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Polymorphic link (entity_type: 'project', 'task', 'milestone')
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(nullable=False, index=True)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Author (denormalized for immutability)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Edit tracking
    is_edited: Mapped[bool] = mapped_column(default=False)
    edited_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    deleted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    author: Mapped["User"] = relationship(foreign_keys=[author_id])

    __table_args__ = (
        Index("ix_project_comments_entity", "entity_type", "entity_id"),
    )

    def __repr__(self) -> str:
        return f"<ProjectComment {self.id} on {self.entity_type}:{self.entity_id}>"


class ProjectActivity(Base):
    """Activity tracking for Project, Task, Milestone - audit trail."""

    __tablename__ = "project_activities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Polymorphic link
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(nullable=False, index=True)

    # Activity details
    activity_type: Mapped[ProjectActivityType] = mapped_column(
        Enum(ProjectActivityType), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Change tracking (from AuditLogger)
    from_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    to_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_fields: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Actor (denormalized for immutability)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Link to main audit log entry (optional)
    audit_log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("audit_logs.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    actor: Mapped[Optional["User"]] = relationship(foreign_keys=[actor_id])

    __table_args__ = (
        Index("ix_project_activities_entity", "entity_type", "entity_id"),
        Index("ix_project_activities_entity_created", "entity_type", "entity_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ProjectActivity {self.activity_type.value} on {self.entity_type}:{self.entity_id}>"


# =============================================================================
# PROJECT TEMPLATES
# =============================================================================


class ProjectTemplate(Base):
    """
    Project template for creating projects with predefined structure.

    Templates include:
    - Project defaults (type, priority, estimated duration)
    - Task templates with offsets and dependencies
    - Milestone templates with offsets
    """
    __tablename__ = "project_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Template info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Project defaults
    project_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_priority: Mapped[Optional[ProjectPriority]] = mapped_column(
        Enum(ProjectPriority), nullable=True
    )
    estimated_duration_days: Mapped[Optional[int]] = mapped_column(nullable=True)
    default_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    # Audit
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(onupdate=datetime.utcnow, nullable=True)

    # Company scope
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Relationships
    created_by: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by_id])
    task_templates: Mapped[List["TaskTemplate"]] = relationship(
        back_populates="project_template", cascade="all, delete-orphan"
    )
    milestone_templates: Mapped[List["MilestoneTemplate"]] = relationship(
        back_populates="project_template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ProjectTemplate {self.name}>"


class TaskTemplate(Base):
    """
    Task template within a project template.

    Defines task structure with day offsets from project start.
    """
    __tablename__ = "task_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_template_id: Mapped[int] = mapped_column(
        ForeignKey("project_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Task details
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # low, medium, high

    # Scheduling (offsets from project start)
    start_day_offset: Mapped[int] = mapped_column(default=0)  # Days from project start
    duration_days: Mapped[int] = mapped_column(default=1)  # Task duration in days

    # Assignment
    default_assigned_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Hierarchy
    parent_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("task_templates.id", ondelete="SET NULL"), nullable=True
    )
    milestone_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("milestone_templates.id", ondelete="SET NULL"), nullable=True
    )
    is_group: Mapped[bool] = mapped_column(default=False)

    # Order
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    project_template: Mapped["ProjectTemplate"] = relationship(back_populates="task_templates")
    parent_template: Mapped[Optional["TaskTemplate"]] = relationship(
        remote_side="TaskTemplate.id", foreign_keys=[parent_template_id]
    )
    milestone_template: Mapped[Optional["MilestoneTemplate"]] = relationship(
        back_populates="task_templates", foreign_keys=[milestone_template_id]
    )

    def __repr__(self) -> str:
        return f"<TaskTemplate {self.subject}>"


class MilestoneTemplate(Base):
    """
    Milestone template within a project template.

    Defines milestone structure with day offsets from project start.
    """
    __tablename__ = "milestone_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_template_id: Mapped[int] = mapped_column(
        ForeignKey("project_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Milestone details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scheduling (offsets from project start)
    start_day_offset: Mapped[int] = mapped_column(default=0)
    end_day_offset: Mapped[int] = mapped_column(default=7)

    # Order
    idx: Mapped[int] = mapped_column(default=0)

    # Relationships
    project_template: Mapped["ProjectTemplate"] = relationship(back_populates="milestone_templates")
    task_templates: Mapped[List["TaskTemplate"]] = relationship(
        back_populates="milestone_template", foreign_keys=[TaskTemplate.milestone_template_id]
    )

    def __repr__(self) -> str:
        return f"<MilestoneTemplate {self.name}>"
