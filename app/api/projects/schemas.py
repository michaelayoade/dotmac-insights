"""
Project Management API Schemas

Provides request/response schemas for:
- Projects and project users
- Tasks and task dependencies
- Milestones
- Comments and activities
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc, asc
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.database import get_db
from app.auth import Require
from app.cache import cached, CACHE_TTL
from app.models import (
    Project,
    ProjectStatus,
    ProjectPriority,
    ProjectType,
    ProjectUser,
    ProjectComment,
    ProjectActivity,
    ProjectActivityType,
    ProjectTemplate,
    TaskTemplate,
    MilestoneTemplate,
    Task,
    TaskStatus,
    TaskPriority,
    TaskDependency,
    Milestone,
    MilestoneStatus,
)
from app.models.customer import Customer
from app.models.employee import Employee

router = APIRouter()

# =============================================================================
# REQUEST SCHEMAS
# =============================================================================


def _log_activity(
    db: Session,
    entity_type: str,
    entity_id: int,
    activity_type: ProjectActivityType,
    description: str,
    actor_id: Optional[int] = None,
    actor_name: Optional[str] = None,
    actor_email: Optional[str] = None,
    from_value: Optional[str] = None,
    to_value: Optional[str] = None,
    changed_fields: Optional[List[str]] = None,
    company: Optional[str] = None,
) -> None:
    activity = ProjectActivity(
        entity_type=entity_type,
        entity_id=entity_id,
        activity_type=activity_type,
        description=description,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_email=actor_email,
        from_value=from_value,
        to_value=to_value,
        changed_fields=changed_fields,
        company=company,
    )
    db.add(activity)


class ProjectUserPayload(BaseModel):
    """Project team member assignment."""

    user: Optional[str] = Field(None, description="User identifier/email")
    full_name: Optional[str] = Field(None, description="User's full name")
    email: Optional[str] = Field(None, description="User's email address")
    project_status: Optional[str] = Field(None, description="User's status on the project")
    view_attachments: Optional[bool] = Field(True, description="Can view project attachments")
    welcome_email_sent: Optional[bool] = Field(False, description="Whether welcome email was sent")
    idx: Optional[int] = Field(0, description="Display order index")


class ProjectCreate(BaseModel):
    """Create a new project.

    Projects track work items, milestones, and team assignments.
    """

    project_name: str = Field(..., description="Project name", min_length=1, max_length=255)
    project_type: Optional[str] = Field(None, description="Project type classification")
    status: Optional[ProjectStatus] = Field(None, description="Current project status")
    priority: Optional[ProjectPriority] = Field(None, description="Project priority level")
    department: Optional[str] = Field(None, description="Owning department")
    company: Optional[str] = Field(None, description="Company code")
    cost_center: Optional[str] = Field(None, description="Cost center for allocation")
    customer_id: Optional[int] = Field(None, description="Associated customer ID")
    project_manager_id: Optional[int] = Field(None, description="Project manager employee ID")
    erpnext_customer: Optional[str] = Field(None, description="ERPNext customer reference")
    erpnext_sales_order: Optional[str] = Field(None, description="ERPNext sales order reference")
    percent_complete: Optional[Decimal] = Field(None, description="Completion percentage (0-100)", ge=0, le=100)
    percent_complete_method: Optional[str] = Field(None, description="How completion is calculated")
    is_active: Optional[str] = Field(None, description="Active status flag")
    actual_time: Optional[Decimal] = Field(None, description="Actual time spent (hours)")
    total_consumed_material_cost: Optional[Decimal] = Field(None, description="Material costs incurred")
    estimated_costing: Optional[Decimal] = Field(None, description="Estimated total cost")
    total_costing_amount: Optional[Decimal] = Field(None, description="Actual total cost")
    total_expense_claim: Optional[Decimal] = Field(None, description="Total expense claims")
    total_purchase_cost: Optional[Decimal] = Field(None, description="Total purchase costs")
    total_sales_amount: Optional[Decimal] = Field(None, description="Total sales value")
    total_billable_amount: Optional[Decimal] = Field(None, description="Total billable amount")
    total_billed_amount: Optional[Decimal] = Field(None, description="Amount already billed")
    gross_margin: Optional[Decimal] = Field(None, description="Gross margin amount")
    per_gross_margin: Optional[Decimal] = Field(None, description="Gross margin percentage")
    collect_progress: Optional[bool] = Field(None, description="Collect progress updates")
    frequency: Optional[str] = Field(None, description="Progress collection frequency")
    message: Optional[str] = Field(None, description="Project message/announcement")
    notes: Optional[str] = Field(None, description="Project notes")
    expected_start_date: Optional[datetime] = Field(None, description="Planned start date")
    expected_end_date: Optional[datetime] = Field(None, description="Planned end date")
    actual_start_date: Optional[datetime] = Field(None, description="Actual start date")
    actual_end_date: Optional[datetime] = Field(None, description="Actual end date")
    from_time: Optional[datetime] = Field(None, description="Daily work start time")
    to_time: Optional[datetime] = Field(None, description="Daily work end time")
    users: Optional[List[ProjectUserPayload]] = Field(default=None, description="Project team members")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_name": "Website Redesign",
                "project_type": "internal",
                "status": "open",
                "priority": "high",
                "department": "Engineering",
                "expected_start_date": "2025-01-15T00:00:00",
                "expected_end_date": "2025-03-31T00:00:00",
            }
        }
    )


class ProjectUpdate(ProjectCreate):
    project_name: Optional[str] = None  # type: ignore[assignment]  # Allow changing the name


class TaskDependencyPayload(BaseModel):
    dependent_task_id: Optional[int] = None
    dependent_task_erpnext: Optional[str] = None
    subject: Optional[str] = None
    project: Optional[str] = None
    idx: Optional[int] = 0


class TaskCreate(BaseModel):
    """Create a new task within a project.

    Tasks represent individual work items that can be assigned, tracked, and completed.
    """

    subject: str = Field(..., description="Task title/subject", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Detailed task description")
    project_id: Optional[int] = Field(None, description="Parent project ID")
    erpnext_project: Optional[str] = Field(None, description="ERPNext project reference")
    issue: Optional[str] = Field(None, description="Related issue/ticket reference")
    task_type: Optional[str] = Field(None, description="Task type classification")
    color: Optional[str] = Field(None, description="Display color for UI", max_length=20)
    status: Optional[TaskStatus] = Field(None, description="Current task status")
    priority: Optional[TaskPriority] = Field(None, description="Task priority level")
    assigned_to: Optional[str] = Field(None, description="Assignee name/email")
    completed_by: Optional[str] = Field(None, description="Who completed the task")
    assigned_to_id: Optional[int] = Field(None, description="Assignee employee ID")
    completed_by_id: Optional[int] = Field(None, description="Completer employee ID")
    progress: Optional[Decimal] = Field(None, description="Completion progress (0-100)", ge=0, le=100)
    expected_time: Optional[Decimal] = Field(None, description="Estimated hours", ge=0)
    actual_time: Optional[Decimal] = Field(None, description="Actual hours spent", ge=0)
    exp_start_date: Optional[date] = Field(None, description="Expected start date")
    exp_end_date: Optional[date] = Field(None, description="Expected end date")
    act_start_date: Optional[date] = Field(None, description="Actual start date")
    act_end_date: Optional[date] = Field(None, description="Actual end date")
    completed_on: Optional[date] = Field(None, description="Completion date")
    review_date: Optional[date] = Field(None, description="Review/check date")
    closing_date: Optional[date] = Field(None, description="Task closing date")
    parent_task: Optional[str] = Field(None, description="Parent task reference")
    parent_task_id: Optional[int] = Field(None, description="Parent task ID for subtasks")
    is_group: Optional[bool] = Field(None, description="True if this is a parent task")
    is_template: Optional[bool] = Field(None, description="True if this is a template task")
    company: Optional[str] = Field(None, description="Company code")
    department: Optional[str] = Field(None, description="Department name")
    total_costing_amount: Optional[Decimal] = Field(None, description="Total cost allocated")
    total_billing_amount: Optional[Decimal] = Field(None, description="Total billable amount")
    total_expense_claim: Optional[Decimal] = Field(None, description="Total expense claims")
    template_task: Optional[str] = Field(None, description="Source template task")
    docstatus: Optional[int] = Field(None, description="Document status")
    depends_on: Optional[List[TaskDependencyPayload]] = Field(default=None, description="Task dependencies")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "Design homepage mockup",
                "project_id": 1,
                "status": "open",
                "priority": "high",
                "assigned_to_id": 5,
                "expected_time": 8,
                "exp_start_date": "2025-01-20",
                "exp_end_date": "2025-01-22",
            }
        }
    )


class TaskUpdate(TaskCreate):
    subject: Optional[str] = None  # type: ignore[assignment]  # Allow updating subject


# =============================================================================
# MILESTONE SCHEMAS
# =============================================================================


class MilestoneCreate(BaseModel):
    """Create a project milestone.

    Milestones mark significant project checkpoints or deliverables.
    """

    name: str = Field(..., description="Milestone name", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Milestone description")
    status: Optional[MilestoneStatus] = Field(None, description="Current milestone status")
    planned_start_date: Optional[date] = Field(None, description="Planned start date")
    planned_end_date: Optional[date] = Field(None, description="Planned completion date")
    actual_start_date: Optional[date] = Field(None, description="Actual start date")
    actual_end_date: Optional[date] = Field(None, description="Actual completion date")
    percent_complete: Optional[Decimal] = Field(None, description="Completion percentage (0-100)", ge=0, le=100)
    idx: Optional[int] = Field(None, description="Display order index")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Phase 1 Complete",
                "description": "All initial development tasks completed",
                "status": "pending",
                "planned_end_date": "2025-02-28",
            }
        }
    )


class MilestoneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[MilestoneStatus] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    actual_start_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    percent_complete: Optional[Decimal] = None
    idx: Optional[int] = None


# =============================================================================
# COMMENT SCHEMAS
# =============================================================================


class CommentCreate(BaseModel):
    """Add a comment to a project or task."""

    content: str = Field(..., description="Comment text content", min_length=1)


class CommentUpdate(BaseModel):
    """Update an existing comment."""

    content: str = Field(..., description="Updated comment text", min_length=1)


