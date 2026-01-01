"""
Schemas Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc, asc
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pydantic import BaseModel, Field

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
    user: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    project_status: Optional[str] = None
    view_attachments: Optional[bool] = True
    welcome_email_sent: Optional[bool] = False
    idx: Optional[int] = 0


class ProjectCreate(BaseModel):
    project_name: str
    project_type: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    department: Optional[str] = None
    company: Optional[str] = None
    cost_center: Optional[str] = None
    customer_id: Optional[int] = None
    project_manager_id: Optional[int] = None
    erpnext_customer: Optional[str] = None
    erpnext_sales_order: Optional[str] = None
    percent_complete: Optional[Decimal] = None
    percent_complete_method: Optional[str] = None
    is_active: Optional[str] = None
    actual_time: Optional[Decimal] = None
    total_consumed_material_cost: Optional[Decimal] = None
    estimated_costing: Optional[Decimal] = None
    total_costing_amount: Optional[Decimal] = None
    total_expense_claim: Optional[Decimal] = None
    total_purchase_cost: Optional[Decimal] = None
    total_sales_amount: Optional[Decimal] = None
    total_billable_amount: Optional[Decimal] = None
    total_billed_amount: Optional[Decimal] = None
    gross_margin: Optional[Decimal] = None
    per_gross_margin: Optional[Decimal] = None
    collect_progress: Optional[bool] = None
    frequency: Optional[str] = None
    message: Optional[str] = None
    notes: Optional[str] = None
    expected_start_date: Optional[datetime] = None
    expected_end_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    users: Optional[List[ProjectUserPayload]] = Field(default=None, description="Project team members")


class ProjectUpdate(ProjectCreate):
    project_name: Optional[str] = None  # type: ignore[assignment]  # Allow changing the name


class TaskDependencyPayload(BaseModel):
    dependent_task_id: Optional[int] = None
    dependent_task_erpnext: Optional[str] = None
    subject: Optional[str] = None
    project: Optional[str] = None
    idx: Optional[int] = 0


class TaskCreate(BaseModel):
    subject: str
    description: Optional[str] = None
    project_id: Optional[int] = None
    erpnext_project: Optional[str] = None
    issue: Optional[str] = None
    task_type: Optional[str] = None
    color: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assigned_to: Optional[str] = None
    completed_by: Optional[str] = None
    assigned_to_id: Optional[int] = None
    completed_by_id: Optional[int] = None
    progress: Optional[Decimal] = None
    expected_time: Optional[Decimal] = None
    actual_time: Optional[Decimal] = None
    exp_start_date: Optional[date] = None
    exp_end_date: Optional[date] = None
    act_start_date: Optional[date] = None
    act_end_date: Optional[date] = None
    completed_on: Optional[date] = None
    review_date: Optional[date] = None
    closing_date: Optional[date] = None
    parent_task: Optional[str] = None
    parent_task_id: Optional[int] = None
    is_group: Optional[bool] = None
    is_template: Optional[bool] = None
    company: Optional[str] = None
    department: Optional[str] = None
    total_costing_amount: Optional[Decimal] = None
    total_billing_amount: Optional[Decimal] = None
    total_expense_claim: Optional[Decimal] = None
    template_task: Optional[str] = None
    docstatus: Optional[int] = None
    depends_on: Optional[List[TaskDependencyPayload]] = Field(default=None, description="Task dependencies")


class TaskUpdate(TaskCreate):
    subject: Optional[str] = None  # type: ignore[assignment]  # Allow updating subject


# =============================================================================
# MILESTONE SCHEMAS
# =============================================================================


class MilestoneCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[MilestoneStatus] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    actual_start_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    percent_complete: Optional[Decimal] = None
    idx: Optional[int] = None


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
    content: str


class CommentUpdate(BaseModel):
    content: str


