"""
Projects Domain Router

Provides all project-related endpoints:
- /dashboard - Project metrics, status distribution
- /projects - List, detail projects with child tables
- /tasks - List, detail tasks with dependencies
- /analytics/* - Project performance, task metrics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract, and_, or_
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, date
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal

from app.database import get_db
from app.models.project import (
    Project, ProjectStatus, ProjectPriority, ProjectUser,
    Milestone, MilestoneStatus, ProjectComment, ProjectActivity, ProjectActivityType,
    ProjectTemplate, TaskTemplate, MilestoneTemplate,
)
from app.models.task import Task, TaskStatus, TaskPriority, TaskDependency
from app.models.expense import Expense
from app.models.customer import Customer
from app.models.employee import Employee
from app.models.auth import User
from app.auth import Require, get_current_user
from app.cache import cached, CACHE_TTL
from app.models.notification import NotificationEventType
from app.models.accounting_ext import AuditLog, AuditAction
from app.services.notification_service import NotificationService
from app.services.audit_logger import AuditLogger

router = APIRouter()


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================


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


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("/dashboard", dependencies=[Depends(Require("analytics:read"))])
@cached("projects-dashboard", ttl=CACHE_TTL["short"])
async def get_projects_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Projects dashboard with project and task metrics.
    """
    # Project counts by status
    project_by_status = db.query(
        Project.status,
        func.count(Project.id).label("count")
    ).filter(Project.is_deleted == False).group_by(Project.status).all()

    status_counts: Dict[str, int] = {
        row.status.value: int(getattr(row, "count", 0) or 0)
        for row in project_by_status
    }
    total_projects: int = sum(status_counts.values())
    active_projects: int = status_counts.get("open", 0)

    # Projects by priority
    by_priority = db.query(
        Project.priority,
        func.count(Project.id).label("count")
    ).filter(
        Project.status == ProjectStatus.OPEN,
        Project.is_deleted == False,
    ).group_by(Project.priority).all()

    priority_counts: Dict[str, int] = {
        row.priority.value: int(getattr(row, "count", 0) or 0)
        for row in by_priority
    }

    # Task counts by status
    task_by_status = db.query(
        Task.status,
        func.count(Task.id).label("count")
    ).group_by(Task.status).all()

    task_status_counts: Dict[str, int] = {
        row.status.value: int(getattr(row, "count", 0) or 0)
        for row in task_by_status
    }
    total_tasks: int = sum(task_status_counts.values())
    open_tasks: int = task_status_counts.get("open", 0) + task_status_counts.get("working", 0)

    # Overdue tasks
    today = date.today()
    overdue_tasks = db.query(func.count(Task.id)).filter(
        Task.exp_end_date < today,
        Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
    ).scalar() or 0

    # Project financials
    total_estimated = db.query(func.sum(Project.estimated_costing)).filter(Project.is_deleted == False).scalar() or Decimal("0")
    total_actual = db.query(func.sum(Project.total_costing_amount)).filter(Project.is_deleted == False).scalar() or Decimal("0")
    total_billed = db.query(func.sum(Project.total_billed_amount)).filter(Project.is_deleted == False).scalar() or Decimal("0")

    # Average completion
    avg_completion = db.query(
        func.avg(Project.percent_complete)
    ).filter(Project.status == ProjectStatus.OPEN, Project.is_deleted == False).scalar() or Decimal("0")

    # Projects due this week
    week_end = datetime.utcnow() + timedelta(days=7)
    due_this_week = db.query(func.count(Project.id)).filter(
        Project.expected_end_date <= week_end,
        Project.expected_end_date >= datetime.utcnow(),
        Project.status == ProjectStatus.OPEN,
        Project.is_deleted == False,
    ).scalar() or 0

    return {
        "projects": {
            "total": total_projects,
            "active": active_projects,
            "completed": status_counts.get("completed", 0),
            "on_hold": status_counts.get("on_hold", 0),
            "cancelled": status_counts.get("cancelled", 0),
        },
        "by_priority": priority_counts,
        "tasks": {
            "total": total_tasks,
            "open": open_tasks,
            "completed": task_status_counts.get("completed", 0),
            "overdue": overdue_tasks,
        },
        "financials": {
            "total_estimated": float(total_estimated),
            "total_actual_cost": float(total_actual),
            "total_billed": float(total_billed),
            "variance": float(total_estimated - total_actual),
        },
        "metrics": {
            "avg_completion_percent": round(float(avg_completion), 1),
            "due_this_week": due_this_week,
        },
    }


# =============================================================================
# PROJECTS LIST & DETAIL
# =============================================================================

@router.get("/projects", dependencies=[Depends(Require("explorer:read"))])
async def list_projects(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    customer_id: Optional[int] = None,
    project_type: Optional[str] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    overdue_only: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List projects with filtering and pagination."""
    query = db.query(Project).filter(Project.is_deleted == False)

    if status:
        try:
            status_enum = ProjectStatus(status)
            query = query.filter(Project.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if priority:
        try:
            priority_enum = ProjectPriority(priority)
            query = query.filter(Project.priority == priority_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    if customer_id:
        query = query.filter(Project.customer_id == customer_id)

    if project_type:
        query = query.filter(Project.project_type == project_type)

    if department:
        query = query.filter(Project.department.ilike(f"%{department}%"))

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Project.project_name.ilike(search_term),
                Project.erpnext_id.ilike(search_term),
            )
        )

    if overdue_only:
        query = query.filter(
            Project.expected_end_date < datetime.utcnow(),
            Project.status == ProjectStatus.OPEN
        )

    if start_date:
        query = query.filter(Project.created_at >= datetime.fromisoformat(start_date))

    if end_date:
        query = query.filter(Project.created_at <= datetime.fromisoformat(end_date))

    total = query.count()
    projects = query.order_by(Project.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": p.id,
                "erpnext_id": p.erpnext_id,
                "project_name": p.project_name,
                "project_type": p.project_type,
                "status": p.status.value if p.status else None,
                "priority": p.priority.value if p.priority else None,
                "department": p.department,
                "customer_id": p.customer_id,
                "percent_complete": float(p.percent_complete) if p.percent_complete else 0,
                "expected_start_date": p.expected_start_date.isoformat() if p.expected_start_date else None,
                "expected_end_date": p.expected_end_date.isoformat() if p.expected_end_date else None,
                "estimated_costing": float(p.estimated_costing) if p.estimated_costing else 0,
                "total_billed_amount": float(p.total_billed_amount) if p.total_billed_amount else 0,
                "is_overdue": p.is_overdue,
                "task_count": len(p.tasks),
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "write_back_status": getattr(p, "write_back_status", None),
            }
            for p in projects
        ],
    }


@router.get("/projects/{project_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed project information with all child tables."""
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get customer info
    customer = None
    if project.customer_id:
        cust = db.query(Customer).filter(Customer.id == project.customer_id).first()
        if cust:
            customer = {
                "id": cust.id,
                "name": cust.name,
                "email": cust.email,
            }

    # Get project manager info
    manager = None
    if project.project_manager_id:
        emp = db.query(Employee).filter(Employee.id == project.project_manager_id).first()
        if emp:
            manager = {
                "id": emp.id,
                "name": emp.name,
                "email": emp.email,
            }

    # Build users list (team members)
    users = [
        {
            "id": u.id,
            "user": u.user,
            "full_name": u.full_name,
            "email": u.email,
            "project_status": u.project_status,
        }
        for u in sorted(project.users, key=lambda x: x.idx or 0)
    ]

    # Build tasks list
    tasks = [
        {
            "id": t.id,
            "erpnext_id": t.erpnext_id,
            "subject": t.subject,
            "status": t.status.value if t.status else None,
            "priority": t.priority.value if t.priority else None,
            "assigned_to": t.assigned_to,
            "progress": float(t.progress) if t.progress else 0,
            "exp_start_date": t.exp_start_date.isoformat() if t.exp_start_date else None,
            "exp_end_date": t.exp_end_date.isoformat() if t.exp_end_date else None,
            "is_overdue": t.is_overdue,
            "dependency_count": len(t.depends_on),
        }
        for t in project.tasks
    ]

    # Build expenses list
    expenses = [
        {
            "id": e.id,
            "erpnext_id": e.erpnext_id,
            "expense_type": e.expense_type,
            "description": e.description,
            "total_claimed_amount": float(e.total_claimed_amount) if e.total_claimed_amount else 0,
            "total_sanctioned_amount": float(e.total_sanctioned_amount) if e.total_sanctioned_amount else 0,
            "status": e.status.value if e.status else None,
            "expense_date": e.expense_date.isoformat() if e.expense_date else None,
            "employee_name": e.employee_name,
        }
        for e in project.expenses
    ]

    # Calculate task statistics
    task_stats = {
        "total": len(tasks),
        "completed": sum(1 for t in project.tasks if t.status == TaskStatus.COMPLETED),
        "open": sum(1 for t in project.tasks if t.status in [TaskStatus.OPEN, TaskStatus.WORKING]),
        "overdue": sum(1 for t in project.tasks if t.is_overdue),
    }

    return {
        "id": project.id,
        "erpnext_id": project.erpnext_id,
        "project_name": project.project_name,
        "project_type": project.project_type,
        "status": project.status.value if project.status else None,
        "priority": project.priority.value if project.priority else None,
        "department": project.department,
        "company": project.company,
        "cost_center": project.cost_center,
        "progress": {
            "percent_complete": float(project.percent_complete) if project.percent_complete else 0,
            "percent_complete_method": project.percent_complete_method,
            "is_active": project.is_active,
        },
        "dates": {
            "expected_start_date": project.expected_start_date.isoformat() if project.expected_start_date else None,
            "expected_end_date": project.expected_end_date.isoformat() if project.expected_end_date else None,
            "actual_start_date": project.actual_start_date.isoformat() if project.actual_start_date else None,
            "actual_end_date": project.actual_end_date.isoformat() if project.actual_end_date else None,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        },
        "financials": {
            "estimated_costing": float(project.estimated_costing) if project.estimated_costing else 0,
            "total_costing_amount": float(project.total_costing_amount) if project.total_costing_amount else 0,
            "total_expense_claim": float(project.total_expense_claim) if project.total_expense_claim else 0,
            "total_purchase_cost": float(project.total_purchase_cost) if project.total_purchase_cost else 0,
            "total_sales_amount": float(project.total_sales_amount) if project.total_sales_amount else 0,
            "total_billable_amount": float(project.total_billable_amount) if project.total_billable_amount else 0,
            "total_billed_amount": float(project.total_billed_amount) if project.total_billed_amount else 0,
            "gross_margin": float(project.gross_margin) if project.gross_margin else 0,
            "profit_margin_percent": float(project.profit_margin_percent),
        },
        "time_tracking": {
            "actual_time": float(project.actual_time) if project.actual_time else 0,
            "total_consumed_material_cost": float(project.total_consumed_material_cost) if project.total_consumed_material_cost else 0,
        },
        "notes": project.notes,
        "is_overdue": project.is_overdue,
        "customer": customer,
        "project_manager": manager,
        "users": users,
        "tasks": tasks,
        "task_stats": task_stats,
        "expenses": expenses,
        "write_back_status": getattr(project, "write_back_status", None),
    }


# =============================================================================
# GANTT CHART DATA
# =============================================================================


@router.get("/projects/{project_id}/gantt", dependencies=[Depends(Require("explorer:read"))])
async def get_project_gantt_data(
    project_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get all tasks with full dependency data for Gantt chart visualization.
    Returns tasks with their dependencies in a format optimized for rendering.
    """
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get all tasks for this project
    tasks = db.query(Task).filter(Task.project_id == project_id).all()

    # Build task list with dependencies
    task_list = []
    min_date = None
    max_date = None

    for task in tasks:
        # Extract dependency IDs
        depends_on_ids = [
            dep.dependent_task_id
            for dep in task.depends_on
            if dep.dependent_task_id is not None
        ]

        task_data = {
            "id": task.id,
            "subject": task.subject,
            "status": task.status.value if task.status else "open",
            "priority": task.priority.value if task.priority else "medium",
            "progress": float(task.progress) if task.progress else 0,
            "exp_start_date": task.exp_start_date.isoformat() if task.exp_start_date else None,
            "exp_end_date": task.exp_end_date.isoformat() if task.exp_end_date else None,
            "assigned_to": task.assigned_to,
            "parent_task_id": task.parent_task_id,
            "is_group": task.is_group,
            "depends_on": depends_on_ids,
        }
        task_list.append(task_data)

        # Track date range
        if task.exp_start_date:
            if min_date is None or task.exp_start_date < min_date:
                min_date = task.exp_start_date
        if task.exp_end_date:
            if max_date is None or task.exp_end_date > max_date:
                max_date = task.exp_end_date

    return {
        "tasks": task_list,
        "date_range": {
            "min_date": min_date.isoformat() if min_date else None,
            "max_date": max_date.isoformat() if max_date else None,
        },
    }


# =============================================================================
# MILESTONES CRUD
# =============================================================================


def _serialize_milestone(milestone: Milestone) -> Dict[str, Any]:
    """Serialize a milestone to a dictionary."""
    return {
        "id": milestone.id,
        "project_id": milestone.project_id,
        "name": milestone.name,
        "description": milestone.description,
        "status": milestone.status.value if milestone.status else None,
        "planned_start_date": milestone.planned_start_date.isoformat() if milestone.planned_start_date else None,
        "planned_end_date": milestone.planned_end_date.isoformat() if milestone.planned_end_date else None,
        "actual_start_date": milestone.actual_start_date.isoformat() if milestone.actual_start_date else None,
        "actual_end_date": milestone.actual_end_date.isoformat() if milestone.actual_end_date else None,
        "percent_complete": float(milestone.percent_complete) if milestone.percent_complete else 0,
        "idx": milestone.idx,
        "is_overdue": milestone.is_overdue,
        "task_count": len(milestone.tasks) if milestone.tasks else 0,
        "created_by_id": milestone.created_by_id,
        "created_at": milestone.created_at.isoformat() if milestone.created_at else None,
        "updated_at": milestone.updated_at.isoformat() if milestone.updated_at else None,
    }


@router.get("/projects/{project_id}/milestones", dependencies=[Depends(Require("explorer:read"))])
async def list_project_milestones(
    project_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all milestones for a project."""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = db.query(Milestone).filter(
        Milestone.project_id == project_id,
        Milestone.is_deleted == False,
    )

    if status:
        try:
            status_enum = MilestoneStatus(status)
            query = query.filter(Milestone.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    milestones = query.order_by(Milestone.idx, Milestone.planned_end_date).all()

    return {
        "total": len(milestones),
        "data": [_serialize_milestone(m) for m in milestones],
    }


@router.post("/projects/{project_id}/milestones", dependencies=[Depends(Require("projects:write"))])
async def create_milestone(
    project_id: int,
    payload: MilestoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new milestone for a project."""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get max idx for ordering
    max_idx = db.query(func.max(Milestone.idx)).filter(
        Milestone.project_id == project_id,
        Milestone.is_deleted == False,
    ).scalar() or 0

    milestone = Milestone(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        status=payload.status or MilestoneStatus.PLANNED,
        planned_start_date=payload.planned_start_date,
        planned_end_date=payload.planned_end_date,
        actual_start_date=payload.actual_start_date,
        actual_end_date=payload.actual_end_date,
        percent_complete=_decimal_or_default(payload.percent_complete),
        idx=payload.idx if payload.idx is not None else max_idx + 1,
        company=project.company,
        created_by_id=current_user.id,
    )

    db.add(milestone)
    db.commit()
    db.refresh(milestone)

    return _serialize_milestone(milestone)


@router.get("/projects/milestones/{milestone_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_milestone(
    milestone_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a specific milestone with associated tasks."""
    milestone = db.query(Milestone).filter(
        Milestone.id == milestone_id,
        Milestone.is_deleted == False,
    ).first()

    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    result = _serialize_milestone(milestone)

    # Include tasks linked to this milestone
    result["tasks"] = [
        {
            "id": t.id,
            "erpnext_id": t.erpnext_id,
            "subject": t.subject,
            "status": t.status.value if t.status else None,
            "priority": t.priority.value if t.priority else None,
            "assigned_to": t.assigned_to,
            "progress": float(t.progress) if t.progress else 0,
            "exp_start_date": t.exp_start_date.isoformat() if t.exp_start_date else None,
            "exp_end_date": t.exp_end_date.isoformat() if t.exp_end_date else None,
            "is_overdue": t.is_overdue,
        }
        for t in milestone.tasks
    ]

    return result


@router.patch("/projects/milestones/{milestone_id}", dependencies=[Depends(Require("projects:write"))])
async def update_milestone(
    milestone_id: int,
    payload: MilestoneUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a milestone."""
    milestone = db.query(Milestone).filter(
        Milestone.id == milestone_id,
        Milestone.is_deleted == False,
    ).first()

    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    if payload.name is not None:
        milestone.name = payload.name
    if payload.description is not None:
        milestone.description = payload.description
    if payload.status is not None:
        milestone.status = payload.status
        # If completed, set actual_end_date if not set
        if payload.status == MilestoneStatus.COMPLETED and not milestone.actual_end_date:
            milestone.actual_end_date = date.today()
    if payload.planned_start_date is not None:
        milestone.planned_start_date = payload.planned_start_date
    if payload.planned_end_date is not None:
        milestone.planned_end_date = payload.planned_end_date
    if payload.actual_start_date is not None:
        milestone.actual_start_date = payload.actual_start_date
    if payload.actual_end_date is not None:
        milestone.actual_end_date = payload.actual_end_date
    if payload.percent_complete is not None:
        milestone.percent_complete = _decimal_or_default(payload.percent_complete)
    if payload.idx is not None:
        milestone.idx = payload.idx

    db.commit()
    db.refresh(milestone)

    return _serialize_milestone(milestone)


@router.delete("/projects/milestones/{milestone_id}", dependencies=[Depends(Require("projects:write"))])
async def delete_milestone(
    milestone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Soft-delete a milestone."""
    milestone = db.query(Milestone).filter(
        Milestone.id == milestone_id,
        Milestone.is_deleted == False,
    ).first()

    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    milestone.is_deleted = True
    milestone.deleted_at = datetime.utcnow()
    milestone.deleted_by_id = current_user.id
    db.commit()

    return {"message": "Milestone deleted", "id": milestone_id}


@router.post("/tasks/{task_id}/milestone", dependencies=[Depends(Require("projects:write"))])
async def assign_task_to_milestone(
    task_id: int,
    milestone_id: Optional[int] = Query(default=None, description="Milestone ID to assign, or null to unassign"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Assign or unassign a task to a milestone."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if milestone_id is not None:
        milestone = db.query(Milestone).filter(
            Milestone.id == milestone_id,
            Milestone.is_deleted == False,
        ).first()
        if not milestone:
            raise HTTPException(status_code=404, detail="Milestone not found")

        # Verify task and milestone belong to same project
        if task.project_id != milestone.project_id:
            raise HTTPException(
                status_code=400,
                detail="Task and milestone must belong to the same project"
            )

    task.milestone_id = milestone_id
    db.commit()

    return {
        "message": "Task milestone updated",
        "task_id": task_id,
        "milestone_id": milestone_id,
    }


# =============================================================================
# PROJECTS CRUD
# =============================================================================


def _decimal_or_default(val: Optional[Decimal], default: Decimal = Decimal("0")) -> Decimal:
    return Decimal(str(val)) if val is not None else default


@router.post("/projects", dependencies=[Depends(Require("projects:write"))])
async def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user=Depends(Require("projects:write")),
) -> Dict[str, Any]:
    """Create a new project with optional team members."""
    project = Project(
        project_name=payload.project_name,
        project_type=payload.project_type,
        status=payload.status or ProjectStatus.OPEN,
        priority=payload.priority or ProjectPriority.MEDIUM,
        department=payload.department,
        company=payload.company,
        cost_center=payload.cost_center,
        customer_id=payload.customer_id,
        project_manager_id=payload.project_manager_id,
        erpnext_customer=payload.erpnext_customer,
        erpnext_sales_order=payload.erpnext_sales_order,
        percent_complete=_decimal_or_default(payload.percent_complete),
        percent_complete_method=payload.percent_complete_method,
        is_active=payload.is_active or "Yes",
        actual_time=_decimal_or_default(payload.actual_time),
        total_consumed_material_cost=_decimal_or_default(payload.total_consumed_material_cost),
        estimated_costing=_decimal_or_default(payload.estimated_costing),
        total_costing_amount=_decimal_or_default(payload.total_costing_amount),
        total_expense_claim=_decimal_or_default(payload.total_expense_claim),
        total_purchase_cost=_decimal_or_default(payload.total_purchase_cost),
        total_sales_amount=_decimal_or_default(payload.total_sales_amount),
        total_billable_amount=_decimal_or_default(payload.total_billable_amount),
        total_billed_amount=_decimal_or_default(payload.total_billed_amount),
        gross_margin=_decimal_or_default(payload.gross_margin),
        per_gross_margin=_decimal_or_default(payload.per_gross_margin),
        collect_progress=bool(payload.collect_progress) if payload.collect_progress is not None else False,
        frequency=payload.frequency,
        message=payload.message,
        notes=payload.notes,
    )

    project.expected_start_date = payload.expected_start_date
    project.expected_end_date = payload.expected_end_date
    project.actual_start_date = payload.actual_start_date
    project.actual_end_date = payload.actual_end_date
    project.from_time = payload.from_time
    project.to_time = payload.to_time

    db.add(project)
    db.flush()

    if payload.users:
        for idx, user in enumerate(payload.users):
            project_user = ProjectUser(
                project_id=project.id,
                user=user.user,
                full_name=user.full_name,
                email=user.email,
                project_status=user.project_status,
                view_attachments=user.view_attachments if user.view_attachments is not None else True,
                welcome_email_sent=user.welcome_email_sent if user.welcome_email_sent is not None else False,
                idx=user.idx if user.idx is not None else idx,
                erpnext_name=None,
            )
            db.add(project_user)

    db.commit()

    # Emit project created notification
    try:
        notif_service = NotificationService(db)
        # Notify project manager and assigned users
        user_ids = []
        if project.project_manager_id:
            user_ids.append(project.project_manager_id)
        for pu in project.users:
            if pu.user:
                pu_user = db.query(User).filter(User.email == pu.email).first()
                if pu_user and pu_user.id not in user_ids:
                    user_ids.append(pu_user.id)

        notif_service.emit_event(
            event_type=NotificationEventType.PROJECT_CREATED,
            payload={
                "project_id": project.id,
                "project_name": project.project_name,
                "created_by_name": user.full_name if hasattr(user, 'full_name') else user.email,
                "expected_end_date": str(project.expected_end_date) if project.expected_end_date else None,
            },
            entity_type="project",
            entity_id=project.id,
            user_ids=user_ids if user_ids else None,
            company=project.company,
        )
    except Exception:
        pass  # Don't fail project creation if notification fails

    return await get_project(project.id, db)


@router.patch("/projects/{project_id}", dependencies=[Depends(Require("projects:write"))])
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a project and optionally replace team members."""
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if payload.project_name is not None:
        project.project_name = payload.project_name
    if payload.project_type is not None:
        project.project_type = payload.project_type
    if payload.status is not None:
        project.status = payload.status
    if payload.priority is not None:
        project.priority = payload.priority
    if payload.department is not None:
        project.department = payload.department
    if payload.company is not None:
        project.company = payload.company
    if payload.cost_center is not None:
        project.cost_center = payload.cost_center
    if payload.customer_id is not None:
        project.customer_id = payload.customer_id
    if payload.project_manager_id is not None:
        project.project_manager_id = payload.project_manager_id
    if payload.erpnext_customer is not None:
        project.erpnext_customer = payload.erpnext_customer
    if payload.erpnext_sales_order is not None:
        project.erpnext_sales_order = payload.erpnext_sales_order
    if payload.percent_complete is not None:
        project.percent_complete = _decimal_or_default(payload.percent_complete)
    if payload.percent_complete_method is not None:
        project.percent_complete_method = payload.percent_complete_method
    if payload.is_active is not None:
        project.is_active = payload.is_active
    if payload.actual_time is not None:
        project.actual_time = _decimal_or_default(payload.actual_time)
    if payload.total_consumed_material_cost is not None:
        project.total_consumed_material_cost = _decimal_or_default(payload.total_consumed_material_cost)
    if payload.estimated_costing is not None:
        project.estimated_costing = _decimal_or_default(payload.estimated_costing)
    if payload.total_costing_amount is not None:
        project.total_costing_amount = _decimal_or_default(payload.total_costing_amount)
    if payload.total_expense_claim is not None:
        project.total_expense_claim = _decimal_or_default(payload.total_expense_claim)
    if payload.total_purchase_cost is not None:
        project.total_purchase_cost = _decimal_or_default(payload.total_purchase_cost)
    if payload.total_sales_amount is not None:
        project.total_sales_amount = _decimal_or_default(payload.total_sales_amount)
    if payload.total_billable_amount is not None:
        project.total_billable_amount = _decimal_or_default(payload.total_billable_amount)
    if payload.total_billed_amount is not None:
        project.total_billed_amount = _decimal_or_default(payload.total_billed_amount)
    if payload.gross_margin is not None:
        project.gross_margin = _decimal_or_default(payload.gross_margin)
    if payload.per_gross_margin is not None:
        project.per_gross_margin = _decimal_or_default(payload.per_gross_margin)
    if payload.collect_progress is not None:
        project.collect_progress = bool(payload.collect_progress)
    if payload.frequency is not None:
        project.frequency = payload.frequency
    if payload.message is not None:
        project.message = payload.message
    if payload.notes is not None:
        project.notes = payload.notes

    if payload.expected_start_date is not None:
        project.expected_start_date = payload.expected_start_date
    if payload.expected_end_date is not None:
        project.expected_end_date = payload.expected_end_date
    if payload.actual_start_date is not None:
        project.actual_start_date = payload.actual_start_date
    if payload.actual_end_date is not None:
        project.actual_end_date = payload.actual_end_date
    if payload.from_time is not None:
        project.from_time = payload.from_time
    if payload.to_time is not None:
        project.to_time = payload.to_time

    if payload.users is not None:
        db.query(ProjectUser).filter(ProjectUser.project_id == project.id).delete(synchronize_session=False)
        for idx, user in enumerate(payload.users):
            project_user = ProjectUser(
                project_id=project.id,
                user=user.user,
                full_name=user.full_name,
                email=user.email,
                project_status=user.project_status,
                view_attachments=user.view_attachments if user.view_attachments is not None else True,
                welcome_email_sent=user.welcome_email_sent if user.welcome_email_sent is not None else False,
                idx=user.idx if user.idx is not None else idx,
                erpnext_name=None,
            )
            db.add(project_user)

    db.commit()
    return await get_project(project.id, db)


@router.delete("/projects/{project_id}", dependencies=[Depends(Require("projects:write"))])
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Soft-delete a project."""
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.is_deleted = True
    project.deleted_at = datetime.utcnow()
    db.commit()
    return {"message": "Project deleted", "id": project_id}


# =============================================================================
# TASKS LIST & DETAIL
# =============================================================================

@router.get("/tasks", dependencies=[Depends(Require("explorer:read"))])
async def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    project_id: Optional[int] = None,
    assigned_to: Optional[str] = None,
    task_type: Optional[str] = None,
    search: Optional[str] = None,
    overdue_only: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List tasks with filtering and pagination."""
    query = db.query(Task)

    if status:
        try:
            status_enum = TaskStatus(status)
            query = query.filter(Task.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if priority:
        try:
            priority_enum = TaskPriority(priority)
            query = query.filter(Task.priority == priority_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    if project_id:
        query = query.filter(Task.project_id == project_id)

    if assigned_to:
        query = query.filter(Task.assigned_to.ilike(f"%{assigned_to}%"))

    if task_type:
        query = query.filter(Task.task_type == task_type)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Task.subject.ilike(search_term),
                Task.erpnext_id.ilike(search_term),
                Task.description.ilike(search_term),
            )
        )

    if overdue_only:
        today = date.today()
        query = query.filter(
            Task.exp_end_date < today,
            Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
        )

    if start_date:
        query = query.filter(Task.created_at >= datetime.fromisoformat(start_date))

    if end_date:
        query = query.filter(Task.created_at <= datetime.fromisoformat(end_date))

    total = query.count()
    tasks = query.order_by(Task.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": t.id,
                "erpnext_id": t.erpnext_id,
                "subject": t.subject,
                "status": t.status.value if t.status else None,
                "priority": t.priority.value if t.priority else None,
                "task_type": t.task_type,
                "project_id": t.project_id,
                "erpnext_project": t.erpnext_project,
                "assigned_to": t.assigned_to,
                "progress": float(t.progress) if t.progress else 0,
                "expected_time": float(t.expected_time) if t.expected_time else 0,
                "actual_time": float(t.actual_time) if t.actual_time else 0,
                "exp_start_date": t.exp_start_date.isoformat() if t.exp_start_date else None,
                "exp_end_date": t.exp_end_date.isoformat() if t.exp_end_date else None,
                "is_overdue": t.is_overdue,
                "dependency_count": len(t.depends_on),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ],
    }


@router.get("/tasks/{task_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed task information with dependencies."""
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get project info
    project = None
    if task.project_id:
        proj = db.query(Project).filter(Project.id == task.project_id).first()
        if proj:
            project = {
                "id": proj.id,
                "erpnext_id": proj.erpnext_id,
                "project_name": proj.project_name,
                "status": proj.status.value if proj.status else None,
            }

    # Get parent task info
    parent = None
    if task.parent_task_id:
        p = db.query(Task).filter(Task.id == task.parent_task_id).first()
        if p:
            parent = {
                "id": p.id,
                "erpnext_id": p.erpnext_id,
                "subject": p.subject,
                "status": p.status.value if p.status else None,
            }

    # Build depends_on list
    depends_on = [
        {
            "id": d.id,
            "dependent_task_id": d.dependent_task_id,
            "dependent_task_erpnext": d.dependent_task_erpnext,
            "subject": d.subject,
            "project": d.project,
        }
        for d in sorted(task.depends_on, key=lambda x: x.idx)
    ]

    # Build sub_tasks list
    sub_tasks = [
        {
            "id": st.id,
            "erpnext_id": st.erpnext_id,
            "subject": st.subject,
            "status": st.status.value if st.status else None,
            "progress": float(st.progress) if st.progress else 0,
        }
        for st in task.sub_tasks
    ]

    # Build expenses list
    expenses = [
        {
            "id": e.id,
            "erpnext_id": e.erpnext_id,
            "expense_type": e.expense_type,
            "total_claimed_amount": float(e.total_claimed_amount) if e.total_claimed_amount else 0,
            "status": e.status.value if e.status else None,
        }
        for e in task.expenses
    ]

    return {
        "id": task.id,
        "erpnext_id": task.erpnext_id,
        "subject": task.subject,
        "description": task.description,
        "status": task.status.value if task.status else None,
        "priority": task.priority.value if task.priority else None,
        "task_type": task.task_type,
        "color": task.color,
        "issue": task.issue,
        "assignment": {
            "assigned_to": task.assigned_to,
            "completed_by": task.completed_by,
        },
        "progress": {
            "progress_percent": float(task.progress) if task.progress else 0,
            "expected_time": float(task.expected_time) if task.expected_time else 0,
            "actual_time": float(task.actual_time) if task.actual_time else 0,
            "time_variance": float(task.time_variance),
        },
        "dates": {
            "exp_start_date": task.exp_start_date.isoformat() if task.exp_start_date else None,
            "exp_end_date": task.exp_end_date.isoformat() if task.exp_end_date else None,
            "act_start_date": task.act_start_date.isoformat() if task.act_start_date else None,
            "act_end_date": task.act_end_date.isoformat() if task.act_end_date else None,
            "completed_on": task.completed_on.isoformat() if task.completed_on else None,
            "review_date": task.review_date.isoformat() if task.review_date else None,
            "closing_date": task.closing_date.isoformat() if task.closing_date else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        },
        "hierarchy": {
            "is_group": task.is_group,
            "is_template": task.is_template,
            "parent_task": task.parent_task,
            "template_task": task.template_task,
        },
        "financials": {
            "total_costing_amount": float(task.total_costing_amount) if task.total_costing_amount else 0,
            "total_billing_amount": float(task.total_billing_amount) if task.total_billing_amount else 0,
            "total_expense_claim": float(task.total_expense_claim) if task.total_expense_claim else 0,
        },
        "organization": {
            "company": task.company,
            "department": task.department,
        },
        "is_overdue": task.is_overdue,
        "project": project,
        "parent_task": parent,
        "depends_on": depends_on,
        "sub_tasks": sub_tasks,
        "expenses": expenses,
    }


# =============================================================================
# TASKS CRUD
# =============================================================================


@router.post("/tasks", dependencies=[Depends(Require("projects:write"))])
async def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new task with optional dependencies."""
    task = Task(
        subject=payload.subject,
        description=payload.description,
        project_id=payload.project_id,
        erpnext_project=payload.erpnext_project,
        issue=payload.issue,
        task_type=payload.task_type,
        color=payload.color,
        status=payload.status or TaskStatus.OPEN,
        priority=payload.priority or TaskPriority.MEDIUM,
        assigned_to=payload.assigned_to,
        completed_by=payload.completed_by,
        progress=_decimal_or_default(payload.progress),
        expected_time=_decimal_or_default(payload.expected_time),
        actual_time=_decimal_or_default(payload.actual_time),
        exp_start_date=payload.exp_start_date,
        exp_end_date=payload.exp_end_date,
        act_start_date=payload.act_start_date,
        act_end_date=payload.act_end_date,
        completed_on=payload.completed_on,
        review_date=payload.review_date,
        closing_date=payload.closing_date,
        parent_task=payload.parent_task,
        parent_task_id=payload.parent_task_id,
        is_group=payload.is_group if payload.is_group is not None else False,
        is_template=payload.is_template if payload.is_template is not None else False,
        company=payload.company,
        department=payload.department,
        total_costing_amount=_decimal_or_default(payload.total_costing_amount),
        total_billing_amount=_decimal_or_default(payload.total_billing_amount),
        total_expense_claim=_decimal_or_default(payload.total_expense_claim),
        template_task=payload.template_task,
        docstatus=payload.docstatus if payload.docstatus is not None else 0,
    )

    db.add(task)
    db.flush()

    if payload.depends_on is not None:
        for idx, dep in enumerate(payload.depends_on):
            dependency = TaskDependency(
                task_id=task.id,
                dependent_task_id=dep.dependent_task_id,
                dependent_task_erpnext=dep.dependent_task_erpnext,
                subject=dep.subject,
                project=dep.project,
                idx=dep.idx if dep.idx is not None else idx,
            )
            db.add(dependency)

    db.commit()
    return await get_task(task.id, db)


@router.patch("/tasks/{task_id}", dependencies=[Depends(Require("projects:write"))])
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a task and optionally replace dependencies."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if payload.subject is not None:
        task.subject = payload.subject
    if payload.description is not None:
        task.description = payload.description
    if payload.project_id is not None:
        task.project_id = payload.project_id
    if payload.erpnext_project is not None:
        task.erpnext_project = payload.erpnext_project
    if payload.issue is not None:
        task.issue = payload.issue
    if payload.task_type is not None:
        task.task_type = payload.task_type
    if payload.color is not None:
        task.color = payload.color
    if payload.status is not None:
        task.status = payload.status
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.assigned_to is not None:
        task.assigned_to = payload.assigned_to
    if payload.completed_by is not None:
        task.completed_by = payload.completed_by
    if payload.progress is not None:
        task.progress = _decimal_or_default(payload.progress)
    if payload.expected_time is not None:
        task.expected_time = _decimal_or_default(payload.expected_time)
    if payload.actual_time is not None:
        task.actual_time = _decimal_or_default(payload.actual_time)
    if payload.exp_start_date is not None:
        task.exp_start_date = payload.exp_start_date
    if payload.exp_end_date is not None:
        task.exp_end_date = payload.exp_end_date
    if payload.act_start_date is not None:
        task.act_start_date = payload.act_start_date
    if payload.act_end_date is not None:
        task.act_end_date = payload.act_end_date
    if payload.completed_on is not None:
        task.completed_on = payload.completed_on
    if payload.review_date is not None:
        task.review_date = payload.review_date
    if payload.closing_date is not None:
        task.closing_date = payload.closing_date
    if payload.parent_task is not None:
        task.parent_task = payload.parent_task
    if payload.parent_task_id is not None:
        task.parent_task_id = payload.parent_task_id
    if payload.is_group is not None:
        task.is_group = payload.is_group
    if payload.is_template is not None:
        task.is_template = payload.is_template
    if payload.company is not None:
        task.company = payload.company
    if payload.department is not None:
        task.department = payload.department
    if payload.total_costing_amount is not None:
        task.total_costing_amount = _decimal_or_default(payload.total_costing_amount)
    if payload.total_billing_amount is not None:
        task.total_billing_amount = _decimal_or_default(payload.total_billing_amount)
    if payload.total_expense_claim is not None:
        task.total_expense_claim = _decimal_or_default(payload.total_expense_claim)
    if payload.template_task is not None:
        task.template_task = payload.template_task
    if payload.docstatus is not None:
        task.docstatus = payload.docstatus

    if payload.depends_on is not None:
        db.query(TaskDependency).filter(TaskDependency.task_id == task.id).delete(synchronize_session=False)
        for idx, dep in enumerate(payload.depends_on):
            dependency = TaskDependency(
                task_id=task.id,
                dependent_task_id=dep.dependent_task_id,
                dependent_task_erpnext=dep.dependent_task_erpnext,
                subject=dep.subject,
                project=dep.project,
                idx=dep.idx if dep.idx is not None else idx,
            )
            db.add(dependency)

    db.commit()
    return await get_task(task.id, db)


@router.delete("/tasks/{task_id}", dependencies=[Depends(Require("projects:write"))])
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a task and its dependencies."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return {"message": "Task deleted", "id": task_id}


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/status-trend", dependencies=[Depends(Require("analytics:read"))])
async def get_project_status_trend(
    months: int = Query(default=12, le=24),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get monthly project creation and completion trend."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=months * 30)

    created = db.query(
        extract("year", Project.created_at).label("year"),
        extract("month", Project.created_at).label("month"),
        func.count(Project.id).label("created"),
    ).filter(
        Project.created_at >= start_dt,
    ).group_by(
        extract("year", Project.created_at),
        extract("month", Project.created_at),
    ).all()

    completed = db.query(
        extract("year", Project.actual_end_date).label("year"),
        extract("month", Project.actual_end_date).label("month"),
        func.count(Project.id).label("completed"),
    ).filter(
        Project.actual_end_date >= start_dt,
        Project.status == ProjectStatus.COMPLETED,
    ).group_by(
        extract("year", Project.actual_end_date),
        extract("month", Project.actual_end_date),
    ).all()

    # Merge data
    data_map: Dict[str, Dict[str, Any]] = {}
    for c in created:
        key = f"{int(c.year)}-{int(c.month):02d}"
        data_map[key] = {"period": key, "year": int(c.year), "month": int(c.month), "created": c.created, "completed": 0}
    for c in completed:
        key = f"{int(c.year)}-{int(c.month):02d}"
        if key in data_map:
            data_map[key]["completed"] = c.completed
        else:
            data_map[key] = {"period": key, "year": int(c.year), "month": int(c.month), "created": 0, "completed": c.completed}

    return sorted(data_map.values(), key=lambda x: x["period"])


@router.get("/analytics/task-distribution", dependencies=[Depends(Require("analytics:read"))])
async def get_task_distribution(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get task distribution by status, priority, and assignee."""
    # By status
    by_status = db.query(
        Task.status,
        func.count(Task.id).label("count"),
    ).group_by(Task.status).all()

    # By priority
    by_priority = db.query(
        Task.priority,
        func.count(Task.id).label("count"),
    ).group_by(Task.priority).all()

    # By assignee (top 10)
    by_assignee = db.query(
        Task.assigned_to,
        func.count(Task.id).label("total"),
        func.sum(case((Task.status == TaskStatus.COMPLETED, 1), else_=0)).label("completed"),
    ).filter(
        Task.assigned_to.isnot(None),
    ).group_by(Task.assigned_to).order_by(func.count(Task.id).desc()).limit(10).all()

    return {
        "by_status": [
            {"status": s.status.value, "count": s.count}
            for s in by_status
        ],
        "by_priority": [
            {"priority": p.priority.value, "count": p.count}
            for p in by_priority
        ],
        "by_assignee": [
            {
                "assignee": a.assigned_to,
                "total": a.total,
                "completed": a.completed,
                "completion_rate": round(a.completed / a.total * 100, 1) if a.total > 0 else 0,
            }
            for a in by_assignee
        ],
    }


@router.get("/analytics/project-performance", dependencies=[Depends(Require("analytics:read"))])
@cached("project-performance", ttl=CACHE_TTL["medium"])
async def get_project_performance(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get project performance metrics including budget and timeline adherence."""
    # Budget performance (projects with both estimated and actual costs)
    budget_data = db.query(
        func.count(Project.id).label("total"),
        func.sum(case(
            (Project.total_costing_amount <= Project.estimated_costing, 1),
            else_=0
        )).label("under_budget"),
        func.sum(case(
            (Project.total_costing_amount > Project.estimated_costing, 1),
            else_=0
        )).label("over_budget"),
    ).filter(
        Project.estimated_costing > 0,
        Project.total_costing_amount > 0,
    ).first()

    # Timeline performance (completed projects)
    timeline_data = db.query(
        func.count(Project.id).label("total"),
        func.sum(case(
            (Project.actual_end_date <= Project.expected_end_date, 1),
            else_=0
        )).label("on_time"),
        func.sum(case(
            (Project.actual_end_date > Project.expected_end_date, 1),
            else_=0
        )).label("delayed"),
    ).filter(
        Project.status == ProjectStatus.COMPLETED,
        Project.expected_end_date.isnot(None),
        Project.actual_end_date.isnot(None),
    ).first()

    # Average project margin
    avg_margin = db.query(
        func.avg(Project.per_gross_margin)
    ).filter(
        Project.total_billed_amount > 0
    ).scalar() or 0

    # Top profitable projects
    top_projects = db.query(Project).filter(
        Project.gross_margin > 0
    ).order_by(Project.gross_margin.desc()).limit(5).all()

    return {
        "budget": {
            "total_analyzed": budget_data.total if budget_data else 0,
            "under_budget": budget_data.under_budget if budget_data else 0,
            "over_budget": budget_data.over_budget if budget_data else 0,
            "adherence_rate": round(
                (budget_data.under_budget / budget_data.total * 100)
                if budget_data and budget_data.total > 0 else 0, 1
            ),
        },
        "timeline": {
            "total_analyzed": timeline_data.total if timeline_data else 0,
            "on_time": timeline_data.on_time if timeline_data else 0,
            "delayed": timeline_data.delayed if timeline_data else 0,
            "on_time_rate": round(
                (timeline_data.on_time / timeline_data.total * 100)
                if timeline_data and timeline_data.total > 0 else 0, 1
            ),
        },
        "profitability": {
            "avg_margin_percent": round(float(avg_margin), 1),
            "top_projects": [
                {
                    "id": p.id,
                    "project_name": p.project_name,
                    "gross_margin": float(p.gross_margin),
                    "margin_percent": float(p.per_gross_margin),
                }
                for p in top_projects
            ],
        },
    }


@router.get("/analytics/department-summary", dependencies=[Depends(Require("analytics:read"))])
async def get_department_summary(
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get project and task summary by department."""
    summary = db.query(
        Project.department,
        func.count(Project.id).label("project_count"),
        func.sum(Project.estimated_costing).label("total_estimated"),
        func.sum(Project.total_billed_amount).label("total_billed"),
        func.avg(Project.percent_complete).label("avg_completion"),
    ).filter(
        Project.department.isnot(None),
        Project.is_deleted == False,
    ).group_by(Project.department).order_by(func.count(Project.id).desc()).limit(15).all()

    result = []
    for s in summary:
        # Get task counts for this department
        task_count = db.query(func.count(Task.id)).join(Project).filter(
            Project.department == s.department
        ).scalar() or 0

        result.append({
            "department": s.department,
            "project_count": s.project_count,
            "task_count": task_count,
            "total_estimated": float(s.total_estimated or 0),
            "total_billed": float(s.total_billed or 0),
            "avg_completion": round(float(s.avg_completion or 0), 1),
        })

    return result


# =============================================================================
# COMMENTS
# =============================================================================

VALID_ENTITY_TYPES = {"project", "task", "milestone"}


def _serialize_comment(comment: ProjectComment) -> Dict[str, Any]:
    """Serialize a comment to a dictionary."""
    return {
        "id": comment.id,
        "entity_type": comment.entity_type,
        "entity_id": comment.entity_id,
        "content": comment.content,
        "author_id": comment.author_id,
        "author_name": comment.author_name,
        "author_email": comment.author_email,
        "is_edited": comment.is_edited,
        "edited_at": comment.edited_at.isoformat() if comment.edited_at else None,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


@router.get("/projects/{entity_type}/{entity_id}/comments", dependencies=[Depends(Require("explorer:read"))])
async def list_entity_comments(
    entity_type: str,
    entity_id: int,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all comments for an entity (project, task, or milestone)."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    query = db.query(ProjectComment).filter(
        ProjectComment.entity_type == entity_type,
        ProjectComment.entity_id == entity_id,
        ProjectComment.is_deleted == False,
    )

    total = query.count()
    comments = query.order_by(ProjectComment.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_comment(c) for c in comments],
    }


@router.post("/projects/{entity_type}/{entity_id}/comments", dependencies=[Depends(Require("projects:write"))])
async def create_comment(
    entity_type: str,
    entity_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new comment on an entity."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    # Verify entity exists
    if entity_type == "project":
        entity = db.query(Project).filter(Project.id == entity_id, Project.is_deleted == False).first()
        company = entity.company if entity else None
    elif entity_type == "task":
        entity = db.query(Task).filter(Task.id == entity_id).first()
        company = entity.company if entity else None
    elif entity_type == "milestone":
        entity = db.query(Milestone).filter(Milestone.id == entity_id, Milestone.is_deleted == False).first()
        company = entity.company if entity else None
    else:
        entity = None
        company = None

    if not entity:
        raise HTTPException(status_code=404, detail=f"{entity_type.capitalize()} not found")

    comment = ProjectComment(
        entity_type=entity_type,
        entity_id=entity_id,
        content=payload.content,
        author_id=current_user.id,
        author_name=current_user.name,
        author_email=current_user.email,
        company=company,
    )

    db.add(comment)

    # Create activity record
    activity = ProjectActivity(
        entity_type=entity_type,
        entity_id=entity_id,
        activity_type=ProjectActivityType.COMMENT_ADDED,
        description=f"Comment added by {current_user.name or current_user.email}",
        actor_id=current_user.id,
        actor_name=current_user.name,
        actor_email=current_user.email,
        company=company,
    )
    db.add(activity)

    db.commit()
    db.refresh(comment)

    return _serialize_comment(comment)


@router.patch("/projects/comments/{comment_id}", dependencies=[Depends(Require("projects:write"))])
async def update_comment(
    comment_id: int,
    payload: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update a comment (only the author can edit)."""
    comment = db.query(ProjectComment).filter(
        ProjectComment.id == comment_id,
        ProjectComment.is_deleted == False,
    ).first()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Only author can edit
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the author can edit this comment")

    comment.content = payload.content
    comment.is_edited = True
    comment.edited_at = datetime.utcnow()

    db.commit()
    db.refresh(comment)

    return _serialize_comment(comment)


@router.delete("/projects/comments/{comment_id}", dependencies=[Depends(Require("projects:write"))])
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Soft-delete a comment (author or admin can delete)."""
    comment = db.query(ProjectComment).filter(
        ProjectComment.id == comment_id,
        ProjectComment.is_deleted == False,
    ).first()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    comment.is_deleted = True
    comment.deleted_at = datetime.utcnow()
    comment.deleted_by_id = current_user.id
    db.commit()

    return {"message": "Comment deleted", "id": comment_id}


# =============================================================================
# ACTIVITY FEED
# =============================================================================


def _serialize_activity(activity: ProjectActivity) -> Dict[str, Any]:
    """Serialize an activity to a dictionary."""
    return {
        "id": activity.id,
        "entity_type": activity.entity_type,
        "entity_id": activity.entity_id,
        "activity_type": activity.activity_type.value if activity.activity_type else None,
        "description": activity.description,
        "from_value": activity.from_value,
        "to_value": activity.to_value,
        "changed_fields": activity.changed_fields,
        "actor_id": activity.actor_id,
        "actor_name": activity.actor_name,
        "actor_email": activity.actor_email,
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
    }


@router.get("/projects/{entity_type}/{entity_id}/activities", dependencies=[Depends(Require("explorer:read"))])
async def list_entity_activities(
    entity_type: str,
    entity_id: int,
    activity_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List activity feed for an entity."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    query = db.query(ProjectActivity).filter(
        ProjectActivity.entity_type == entity_type,
        ProjectActivity.entity_id == entity_id,
    )

    if activity_type:
        try:
            activity_type_enum = ProjectActivityType(activity_type)
            query = query.filter(ProjectActivity.activity_type == activity_type_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid activity type: {activity_type}")

    total = query.count()
    activities = query.order_by(ProjectActivity.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_activity(a) for a in activities],
    }


@router.get("/projects/{project_id}/activity-timeline", dependencies=[Depends(Require("explorer:read"))])
async def get_project_activity_timeline(
    project_id: int,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get combined activity timeline for a project including its tasks and milestones."""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get task IDs for this project
    task_ids = [t.id for t in project.tasks]
    milestone_ids = [m.id for m in project.milestones if not m.is_deleted]

    # Build combined query for all activities
    query = db.query(ProjectActivity).filter(
        or_(
            and_(ProjectActivity.entity_type == "project", ProjectActivity.entity_id == project_id),
            and_(ProjectActivity.entity_type == "task", ProjectActivity.entity_id.in_(task_ids)) if task_ids else False,
            and_(ProjectActivity.entity_type == "milestone", ProjectActivity.entity_id.in_(milestone_ids)) if milestone_ids else False,
        )
    )

    activities = query.order_by(ProjectActivity.created_at.desc()).limit(limit).all()

    return {
        "project_id": project_id,
        "total": len(activities),
        "data": [_serialize_activity(a) for a in activities],
    }


# =============================================================================
# ATTACHMENTS
# =============================================================================

from fastapi import UploadFile, File, Form
import os
import uuid

from app.models.document_attachment import DocumentAttachment

# Configuration
UPLOAD_DIR = "/tmp/attachments/projects"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".zip"}

# Valid entity types for attachments
ATTACHMENT_ENTITY_TYPES = {"project", "task", "milestone"}


def _serialize_attachment(a: DocumentAttachment) -> Dict[str, Any]:
    """Serialize attachment to dict."""
    return {
        "id": a.id,
        "file_name": a.file_name,
        "file_type": a.file_type,
        "file_size": a.file_size,
        "attachment_type": a.attachment_type,
        "is_primary": a.is_primary,
        "description": a.description,
        "uploaded_at": a.uploaded_at.isoformat() if a.uploaded_at else None,
        "uploaded_by_id": a.uploaded_by_id,
    }


@router.get("/projects/{entity_type}/{entity_id}/attachments", dependencies=[Depends(Require("explorer:read"))])
async def list_entity_attachments(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List attachments for a project entity (project, task, or milestone)."""
    if entity_type not in ATTACHMENT_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid entity type. Must be one of: {ATTACHMENT_ENTITY_TYPES}")

    doctype = f"project_{entity_type}"  # e.g., "project_project", "project_task", "project_milestone"

    attachments = db.query(DocumentAttachment).filter(
        DocumentAttachment.doctype == doctype,
        DocumentAttachment.document_id == entity_id,
    ).order_by(DocumentAttachment.uploaded_at.desc()).all()

    return {
        "total": len(attachments),
        "data": [_serialize_attachment(a) for a in attachments],
    }


@router.post("/projects/{entity_type}/{entity_id}/attachments", dependencies=[Depends(Require("projects:write"))])
async def upload_entity_attachment(
    entity_type: str,
    entity_id: int,
    file: UploadFile = File(...),
    attachment_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_primary: bool = Form(False),
    db: Session = Depends(get_db),
    user=Depends(Require("projects:write")),
) -> Dict[str, Any]:
    """Upload an attachment for a project entity."""
    if entity_type not in ATTACHMENT_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid entity type. Must be one of: {ATTACHMENT_ENTITY_TYPES}")

    # Verify entity exists
    if entity_type == "project":
        entity = db.query(Project).filter(Project.id == entity_id, Project.is_deleted == False).first()
    elif entity_type == "task":
        entity = db.query(Task).filter(Task.id == entity_id).first()
    elif entity_type == "milestone":
        entity = db.query(Milestone).filter(Milestone.id == entity_id, Milestone.is_deleted == False).first()
    else:
        entity = None

    if not entity:
        raise HTTPException(status_code=404, detail=f"{entity_type.capitalize()} not found")

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # Generate unique filename
    unique_id = uuid.uuid4().hex[:8]
    safe_filename = f"{unique_id}_{file.filename}"

    # Create upload directory
    doctype = f"project_{entity_type}"
    doc_dir = os.path.join(UPLOAD_DIR, entity_type, str(entity_id))
    os.makedirs(doc_dir, exist_ok=True)

    # Save file
    file_path = os.path.join(doc_dir, safe_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # If setting as primary, unset any existing primary
    if is_primary:
        db.query(DocumentAttachment).filter(
            DocumentAttachment.doctype == doctype,
            DocumentAttachment.document_id == entity_id,
            DocumentAttachment.is_primary == True,
        ).update({"is_primary": False})

    # Create attachment record
    attachment = DocumentAttachment(
        doctype=doctype,
        document_id=entity_id,
        file_name=file.filename,
        file_path=file_path,
        file_type=file.content_type,
        file_size=file_size,
        attachment_type=attachment_type,
        is_primary=is_primary,
        description=description,
        uploaded_by_id=user.id if hasattr(user, "id") else None,
    )
    db.add(attachment)

    # Log activity
    _log_activity(
        db=db,
        entity_type=entity_type,
        entity_id=entity_id,
        activity_type=ProjectActivityType.ATTACHMENT_ADDED,
        description=f"Attachment '{file.filename}' added",
        actor_id=user.id if hasattr(user, "id") else None,
        actor_name=user.name if hasattr(user, "name") else None,
        actor_email=user.email if hasattr(user, "email") else None,
    )

    db.commit()
    db.refresh(attachment)

    return {
        "message": "Attachment uploaded",
        "id": attachment.id,
        "file_name": attachment.file_name,
        "file_size": attachment.file_size,
    }


@router.get("/projects/attachments/{attachment_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get attachment details."""
    attachment = db.query(DocumentAttachment).filter(
        DocumentAttachment.id == attachment_id,
        DocumentAttachment.doctype.startswith("project_"),
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    return {
        "id": attachment.id,
        "doctype": attachment.doctype,
        "document_id": attachment.document_id,
        "file_name": attachment.file_name,
        "file_path": attachment.file_path,
        "file_type": attachment.file_type,
        "file_size": attachment.file_size,
        "attachment_type": attachment.attachment_type,
        "is_primary": attachment.is_primary,
        "description": attachment.description,
        "uploaded_at": attachment.uploaded_at.isoformat() if attachment.uploaded_at else None,
        "uploaded_by_id": attachment.uploaded_by_id,
    }


@router.delete("/projects/attachments/{attachment_id}", dependencies=[Depends(Require("projects:write"))])
async def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("projects:write")),
) -> Dict[str, Any]:
    """Delete an attachment."""
    attachment = db.query(DocumentAttachment).filter(
        DocumentAttachment.id == attachment_id,
        DocumentAttachment.doctype.startswith("project_"),
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Delete file from disk
    if os.path.exists(attachment.file_path):
        try:
            os.remove(attachment.file_path)
        except OSError:
            pass  # File might already be deleted

    # Extract entity info for activity log
    entity_type = attachment.doctype.replace("project_", "")
    entity_id = attachment.document_id
    file_name = attachment.file_name

    db.delete(attachment)
    db.commit()

    return {"message": "Attachment deleted", "id": attachment_id}


@router.get("/projects/attachments/{attachment_id}/download", dependencies=[Depends(Require("explorer:read"))])
async def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
):
    """Download an attachment file."""
    from fastapi.responses import FileResponse

    attachment = db.query(DocumentAttachment).filter(
        DocumentAttachment.id == attachment_id,
        DocumentAttachment.doctype.startswith("project_"),
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if not os.path.exists(attachment.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=attachment.file_path,
        filename=attachment.file_name,
        media_type=attachment.file_type or "application/octet-stream",
    )


# =============================================================================
# APPROVAL WORKFLOWS
# =============================================================================

from app.services.approval_engine import (
    ApprovalEngine,
    WorkflowNotFoundError,
    ApprovalNotFoundError,
    UnauthorizedApprovalError,
    InvalidStateError,
)


class ApprovalSubmitPayload(BaseModel):
    """Payload for submitting a project for approval."""
    remarks: Optional[str] = None


class ApprovalActionPayload(BaseModel):
    """Payload for approve/reject actions."""
    remarks: Optional[str] = None
    reason: Optional[str] = None  # Required for rejection


@router.get("/projects/{project_id}/approval-status", dependencies=[Depends(Require("explorer:read"))])
async def get_project_approval_status(
    project_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get the approval status for a project."""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    engine = ApprovalEngine(db)
    status = engine.get_approval_status("project", project_id)

    if not status:
        return {
            "project_id": project_id,
            "has_approval": False,
            "status": None,
            "message": "No approval workflow initiated for this project",
        }

    return {
        "project_id": project_id,
        "has_approval": True,
        **status,
    }


@router.post("/projects/{project_id}/submit-approval", dependencies=[Depends(Require("projects:write"))])
async def submit_project_for_approval(
    project_id: int,
    payload: ApprovalSubmitPayload = None,
    db: Session = Depends(get_db),
    user=Depends(Require("projects:write")),
) -> Dict[str, Any]:
    """Submit a project for approval."""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    engine = ApprovalEngine(db)

    try:
        approval = engine.submit_document(
            doctype="project",
            document_id=project_id,
            user_id=user.id,
            amount=project.estimated_costing,
            document_name=project.project_name,
        )

        # Log activity
        _log_activity(
            db=db,
            entity_type="project",
            entity_id=project_id,
            activity_type=ProjectActivityType.APPROVAL_SUBMITTED,
            description=f"Project submitted for approval",
            actor_id=user.id,
            actor_name=user.name if hasattr(user, "name") else None,
            actor_email=user.email if hasattr(user, "email") else None,
        )

        db.commit()

        # Emit notification for approval request
        try:
            notif_service = NotificationService(db)
            # Find approvers who can approve this step
            approver_ids = engine.get_pending_approvers(approval.id)
            if approver_ids:
                notif_service.emit_event(
                    event_type=NotificationEventType.PROJECT_APPROVAL_REQUESTED,
                    payload={
                        "project_id": project_id,
                        "project_name": project.project_name,
                        "requester_name": user.name if hasattr(user, "name") else user.email,
                        "estimated_costing": float(project.estimated_costing) if project.estimated_costing else None,
                    },
                    entity_type="project",
                    entity_id=project_id,
                    user_ids=approver_ids,
                    company=project.company,
                )
        except Exception:
            pass

        return {
            "message": "Project submitted for approval",
            "project_id": project_id,
            "approval_id": approval.id,
            "status": approval.status.value,
        }

    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/approve", dependencies=[Depends(Require("approvals:approve"))])
async def approve_project(
    project_id: int,
    payload: ApprovalActionPayload = None,
    db: Session = Depends(get_db),
    user=Depends(Require("approvals:approve")),
) -> Dict[str, Any]:
    """Approve a project at the current approval step."""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    engine = ApprovalEngine(db)
    remarks = payload.remarks if payload else None

    try:
        approval = engine.approve_document(
            doctype="project",
            document_id=project_id,
            user_id=user.id,
            remarks=remarks,
        )

        # Log activity
        _log_activity(
            db=db,
            entity_type="project",
            entity_id=project_id,
            activity_type=ProjectActivityType.APPROVAL_APPROVED,
            description=f"Project approved at step {approval.current_step}",
            actor_id=user.id,
            actor_name=user.name if hasattr(user, "name") else None,
            actor_email=user.email if hasattr(user, "email") else None,
        )

        db.commit()

        # Emit notification for approval
        try:
            notif_service = NotificationService(db)
            # Notify the project submitter/manager
            notify_ids = []
            if approval.submitted_by_id:
                notify_ids.append(approval.submitted_by_id)
            if project.project_manager_id and project.project_manager_id not in notify_ids:
                notify_ids.append(project.project_manager_id)

            if notify_ids:
                notif_service.emit_event(
                    event_type=NotificationEventType.PROJECT_APPROVED,
                    payload={
                        "project_id": project_id,
                        "project_name": project.project_name,
                        "approver_name": user.name if hasattr(user, "name") else user.email,
                        "remarks": remarks,
                    },
                    entity_type="project",
                    entity_id=project_id,
                    user_ids=notify_ids,
                    company=project.company,
                )
        except Exception:
            pass

        return {
            "message": "Project approved",
            "project_id": project_id,
            "approval_id": approval.id,
            "status": approval.status.value,
            "current_step": approval.current_step,
        }

    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedApprovalError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/reject", dependencies=[Depends(Require("approvals:approve"))])
async def reject_project(
    project_id: int,
    payload: ApprovalActionPayload,
    db: Session = Depends(get_db),
    user=Depends(Require("approvals:approve")),
) -> Dict[str, Any]:
    """Reject a project."""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not payload.reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    engine = ApprovalEngine(db)

    try:
        approval = engine.reject_document(
            doctype="project",
            document_id=project_id,
            user_id=user.id,
            reason=payload.reason,
        )

        # Log activity
        _log_activity(
            db=db,
            entity_type="project",
            entity_id=project_id,
            activity_type=ProjectActivityType.APPROVAL_REJECTED,
            description=f"Project rejected: {payload.reason[:100]}",
            actor_id=user.id,
            actor_name=user.name if hasattr(user, "name") else None,
            actor_email=user.email if hasattr(user, "email") else None,
        )

        db.commit()

        # Emit notification for rejection
        try:
            notif_service = NotificationService(db)
            # Notify the project submitter/manager
            notify_ids = []
            if approval.submitted_by_id:
                notify_ids.append(approval.submitted_by_id)
            if project.project_manager_id and project.project_manager_id not in notify_ids:
                notify_ids.append(project.project_manager_id)

            if notify_ids:
                notif_service.emit_event(
                    event_type=NotificationEventType.PROJECT_REJECTED,
                    payload={
                        "project_id": project_id,
                        "project_name": project.project_name,
                        "rejector_name": user.name if hasattr(user, "name") else user.email,
                        "reason": payload.reason,
                    },
                    entity_type="project",
                    entity_id=project_id,
                    user_ids=notify_ids,
                    company=project.company,
                )
        except Exception:
            pass

        return {
            "message": "Project rejected",
            "project_id": project_id,
            "approval_id": approval.id,
            "status": approval.status.value,
            "reason": payload.reason,
        }

    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedApprovalError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidStateError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/can-approve", dependencies=[Depends(Require("explorer:read"))])
async def check_can_approve_project(
    project_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Check if the current user can approve a project."""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    engine = ApprovalEngine(db)
    can_approve = engine.can_user_approve("project", project_id, user.id)

    return {
        "project_id": project_id,
        "user_id": user.id,
        "can_approve": can_approve,
    }


# =============================================================================
# CHANGE HISTORY
# =============================================================================


@router.get("/projects/{entity_type}/{entity_id}/history", dependencies=[Depends(Require("explorer:read"))])
async def get_entity_history(
    entity_type: str,
    entity_id: int,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get change history for a project entity (project, task, or milestone)."""
    if entity_type not in ("project", "task", "milestone"):
        raise HTTPException(status_code=400, detail="Invalid entity type")

    # Verify entity exists
    if entity_type == "project":
        entity = db.query(Project).filter(Project.id == entity_id, Project.is_deleted == False).first()
    elif entity_type == "task":
        entity = db.query(Task).filter(Task.id == entity_id, Task.is_deleted == False).first()
    else:
        entity = db.query(Milestone).filter(Milestone.id == entity_id, Milestone.is_deleted == False).first()

    if not entity:
        raise HTTPException(status_code=404, detail=f"{entity_type.capitalize()} not found")

    # Get audit history
    audit_logger = AuditLogger(db)
    audit_entries = audit_logger.get_document_history(
        doctype=f"project_{entity_type}" if entity_type != "project" else "project",
        document_id=entity_id,
        limit=limit,
        offset=offset,
    )

    # Also get activity from ProjectActivity for a combined view
    activities = (
        db.query(ProjectActivity)
        .filter(
            ProjectActivity.entity_type == entity_type,
            ProjectActivity.entity_id == entity_id,
        )
        .order_by(ProjectActivity.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Combine and format
    history = []

    for audit in audit_entries:
        history.append({
            "id": f"audit-{audit.id}",
            "source": "audit",
            "timestamp": audit.timestamp.isoformat() if audit.timestamp else None,
            "action": audit.action.value if audit.action else None,
            "actor_id": audit.user_id,
            "actor_name": audit.user_name,
            "actor_email": audit.user_email,
            "changed_fields": audit.changed_fields,
            "old_values": audit.old_values,
            "new_values": audit.new_values,
            "remarks": audit.remarks,
        })

    for activity in activities:
        history.append({
            "id": f"activity-{activity.id}",
            "source": "activity",
            "timestamp": activity.created_at.isoformat() if activity.created_at else None,
            "action": activity.activity_type.value if activity.activity_type else None,
            "actor_id": activity.actor_id,
            "actor_name": activity.actor_name,
            "actor_email": activity.actor_email,
            "description": activity.description,
            "from_value": activity.from_value,
            "to_value": activity.to_value,
            "changed_fields": activity.changed_fields,
        })

    # Sort by timestamp descending
    history.sort(key=lambda x: x["timestamp"] or "", reverse=True)

    # Apply limit after merge
    history = history[:limit]

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "total": len(history),
        "data": history,
    }


# =============================================================================
# PROJECT TEMPLATES
# =============================================================================


class TaskTemplatePayload(BaseModel):
    """Task template payload."""
    subject: str
    description: Optional[str] = None
    priority: Optional[str] = None
    start_day_offset: int = 0
    duration_days: int = 1
    default_assigned_role: Optional[str] = None
    is_group: bool = False
    idx: int = 0


class MilestoneTemplatePayload(BaseModel):
    """Milestone template payload."""
    name: str
    description: Optional[str] = None
    start_day_offset: int = 0
    end_day_offset: int = 7
    idx: int = 0


class ProjectTemplateCreate(BaseModel):
    """Create project template payload."""
    name: str
    description: Optional[str] = None
    project_type: Optional[str] = None
    default_priority: Optional[ProjectPriority] = None
    estimated_duration_days: Optional[int] = None
    default_notes: Optional[str] = None
    is_active: Optional[bool] = None
    task_templates: Optional[List[TaskTemplatePayload]] = Field(default=None, alias="tasks")
    milestone_templates: Optional[List[MilestoneTemplatePayload]] = Field(default=None, alias="milestones")

    model_config = ConfigDict(populate_by_name=True)


class ProjectTemplateUpdate(BaseModel):
    """Update project template payload."""
    name: Optional[str] = None
    description: Optional[str] = None
    project_type: Optional[str] = None
    default_priority: Optional[ProjectPriority] = None
    estimated_duration_days: Optional[int] = None
    default_notes: Optional[str] = None
    is_active: Optional[bool] = None
    task_templates: Optional[List[TaskTemplatePayload]] = Field(default=None, alias="tasks")
    milestone_templates: Optional[List[MilestoneTemplatePayload]] = Field(default=None, alias="milestones")

    model_config = ConfigDict(populate_by_name=True)


def _validate_task_template_priority(priority: Optional[str]) -> Optional[str]:
    """Validate task template priority values to avoid invalid enums later."""
    if priority is None:
        return None
    try:
        TaskPriority(priority)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid task template priority: {priority}")
    return priority


def _serialize_template(template: ProjectTemplate) -> Dict[str, Any]:
    """Serialize project template to dict."""
    task_templates = [
        {
            "id": t.id,
            "subject": t.subject,
            "description": t.description,
            "priority": t.priority,
            "start_day_offset": t.start_day_offset,
            "duration_days": t.duration_days,
            "default_assigned_role": t.default_assigned_role,
            "is_group": t.is_group,
            "idx": t.idx,
        }
        for t in sorted(template.task_templates, key=lambda x: x.idx)
    ]
    milestone_templates = [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "start_day_offset": m.start_day_offset,
            "end_day_offset": m.end_day_offset,
            "idx": m.idx,
        }
        for m in sorted(template.milestone_templates, key=lambda x: x.idx)
    ]
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "project_type": template.project_type,
        "default_priority": template.default_priority.value if template.default_priority else None,
        "estimated_duration_days": template.estimated_duration_days,
        "default_notes": template.default_notes,
        "is_active": template.is_active,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "task_count": len(template.task_templates),
        "milestone_count": len(template.milestone_templates),
        "task_templates": task_templates,
        "milestone_templates": milestone_templates,
        "tasks": task_templates,
        "milestones": milestone_templates,
    }


@router.get("/projects/templates", dependencies=[Depends(Require("explorer:read"))])
async def list_project_templates(
    active_only: bool = Query(default=True),
    is_active: Optional[bool] = Query(default=None),
    project_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all project templates."""
    query = db.query(ProjectTemplate)

    if is_active is not None:
        query = query.filter(ProjectTemplate.is_active == is_active)
    elif active_only:
        query = query.filter(ProjectTemplate.is_active == True)

    if project_type:
        query = query.filter(ProjectTemplate.project_type == project_type)

    total = query.count()
    templates = query.order_by(ProjectTemplate.name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_template(t) for t in templates],
    }


@router.post("/projects/templates", dependencies=[Depends(Require("projects:admin"))])
async def create_project_template(
    payload: ProjectTemplateCreate,
    db: Session = Depends(get_db),
    user=Depends(Require("projects:admin")),
) -> Dict[str, Any]:
    """Create a new project template."""
    template = ProjectTemplate(
        name=payload.name,
        description=payload.description,
        project_type=payload.project_type,
        default_priority=payload.default_priority,
        estimated_duration_days=payload.estimated_duration_days,
        default_notes=payload.default_notes,
        is_active=payload.is_active if payload.is_active is not None else True,
        created_by_id=user.id,
    )
    db.add(template)
    db.flush()

    # Add task templates
    if payload.task_templates:
        for idx, tt in enumerate(payload.task_templates):
            task_template = TaskTemplate(
                project_template_id=template.id,
                subject=tt.subject,
                description=tt.description,
                priority=_validate_task_template_priority(tt.priority),
                start_day_offset=tt.start_day_offset,
                duration_days=tt.duration_days,
                default_assigned_role=tt.default_assigned_role,
                is_group=tt.is_group,
                idx=tt.idx or idx,
            )
            db.add(task_template)

    # Add milestone templates
    if payload.milestone_templates:
        for idx, mt in enumerate(payload.milestone_templates):
            milestone_template = MilestoneTemplate(
                project_template_id=template.id,
                name=mt.name,
                description=mt.description,
                start_day_offset=mt.start_day_offset,
                end_day_offset=mt.end_day_offset,
                idx=mt.idx or idx,
            )
            db.add(milestone_template)

    db.commit()
    db.refresh(template)

    return {
        "message": "Template created",
        "id": template.id,
        "template": _serialize_template(template),
    }


@router.get("/projects/templates/{template_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_project_template(
    template_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a project template by ID."""
    template = db.query(ProjectTemplate).filter(ProjectTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return _serialize_template(template)


@router.patch("/projects/templates/{template_id}", dependencies=[Depends(Require("projects:admin"))])
async def update_project_template(
    template_id: int,
    payload: ProjectTemplateUpdate,
    db: Session = Depends(get_db),
    user=Depends(Require("projects:admin")),
) -> Dict[str, Any]:
    """Update a project template."""
    template = db.query(ProjectTemplate).filter(ProjectTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Update fields
    if payload.name is not None:
        template.name = payload.name
    if payload.description is not None:
        template.description = payload.description
    if payload.project_type is not None:
        template.project_type = payload.project_type
    if payload.default_priority is not None:
        template.default_priority = payload.default_priority
    if payload.estimated_duration_days is not None:
        template.estimated_duration_days = payload.estimated_duration_days
    if payload.default_notes is not None:
        template.default_notes = payload.default_notes
    if payload.is_active is not None:
        template.is_active = payload.is_active
    if payload.task_templates is not None:
        template.task_templates.clear()
        for idx, tt in enumerate(payload.task_templates):
            task_template = TaskTemplate(
                project_template_id=template.id,
                subject=tt.subject,
                description=tt.description,
                priority=_validate_task_template_priority(tt.priority),
                start_day_offset=tt.start_day_offset,
                duration_days=tt.duration_days,
                default_assigned_role=tt.default_assigned_role,
                is_group=tt.is_group,
                idx=tt.idx or idx,
            )
            db.add(task_template)
    if payload.milestone_templates is not None:
        template.milestone_templates.clear()
        for idx, mt in enumerate(payload.milestone_templates):
            milestone_template = MilestoneTemplate(
                project_template_id=template.id,
                name=mt.name,
                description=mt.description,
                start_day_offset=mt.start_day_offset,
                end_day_offset=mt.end_day_offset,
                idx=mt.idx or idx,
            )
            db.add(milestone_template)

    db.commit()
    db.refresh(template)

    return {
        "message": "Template updated",
        "template": _serialize_template(template),
    }


@router.delete("/projects/templates/{template_id}", dependencies=[Depends(Require("projects:admin"))])
async def delete_project_template(
    template_id: int,
    db: Session = Depends(get_db),
    user=Depends(Require("projects:admin")),
) -> Dict[str, Any]:
    """Delete a project template."""
    template = db.query(ProjectTemplate).filter(ProjectTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    db.delete(template)
    db.commit()

    return {"message": "Template deleted", "id": template_id}


class CreateFromTemplatePayload(BaseModel):
    """Payload for creating a project from a template."""
    project_name: str
    expected_start_date: Optional[date] = None
    customer_id: Optional[int] = None
    project_manager_id: Optional[int] = None
    notes: Optional[str] = None


@router.post("/projects/from-template/{template_id}", dependencies=[Depends(Require("projects:write"))])
async def create_project_from_template(
    template_id: int,
    payload: CreateFromTemplatePayload,
    db: Session = Depends(get_db),
    user=Depends(Require("projects:write")),
) -> Dict[str, Any]:
    """Create a new project from a template."""
    template = db.query(ProjectTemplate).filter(
        ProjectTemplate.id == template_id,
        ProjectTemplate.is_active == True,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found or inactive")

    # Calculate dates
    start_date = payload.expected_start_date or date.today()
    end_date = None
    if template.estimated_duration_days:
        end_date = start_date + timedelta(days=template.estimated_duration_days)

    # Create project
    project = Project(
        project_name=payload.project_name,
        project_type=template.project_type,
        priority=template.default_priority,
        status=ProjectStatus.OPEN,
        expected_start_date=start_date,
        expected_end_date=end_date,
        notes=payload.notes or template.default_notes,
        customer_id=payload.customer_id,
        project_manager_id=payload.project_manager_id,
    )
    db.add(project)
    db.flush()

    # Create milestones from template
    milestone_map = {}  # template_id -> created_milestone
    for mt in sorted(template.milestone_templates, key=lambda x: x.idx):
        milestone = Milestone(
            project_id=project.id,
            name=mt.name,
            description=mt.description,
            status=MilestoneStatus.PLANNED,
            planned_start_date=start_date + timedelta(days=mt.start_day_offset),
            planned_end_date=start_date + timedelta(days=mt.end_day_offset),
            idx=mt.idx,
            created_by_id=user.id,
        )
        db.add(milestone)
        db.flush()
        milestone_map[mt.id] = milestone

    # Create tasks from template
    for tt in sorted(template.task_templates, key=lambda x: x.idx):
        task_priority = TaskPriority.MEDIUM
        if tt.priority:
            try:
                task_priority = TaskPriority(tt.priority)
            except ValueError:
                task_priority = TaskPriority.MEDIUM
        task = Task(
            project_id=project.id,
            subject=tt.subject,
            description=tt.description,
            priority=task_priority,
            status=TaskStatus.OPEN,
            exp_start_date=start_date + timedelta(days=tt.start_day_offset),
            exp_end_date=start_date + timedelta(days=tt.start_day_offset + tt.duration_days),
            is_group=tt.is_group,
            milestone_id=milestone_map.get(tt.milestone_template_id).id if tt.milestone_template_id and tt.milestone_template_id in milestone_map else None,
        )
        db.add(task)

    # Log activity
    _log_activity(
        db=db,
        entity_type="project",
        entity_id=project.id,
        activity_type=ProjectActivityType.CREATED,
        description=f"Project created from template: {template.name}",
        actor_id=user.id,
        actor_name=user.name if hasattr(user, "name") else None,
        actor_email=user.email if hasattr(user, "email") else None,
    )

    db.commit()
    db.refresh(project)

    return {
        "message": "Project created from template",
        "project_id": project.id,
        "project_name": project.project_name,
        "template_id": template_id,
        "milestones_created": len(milestone_map),
        "tasks_created": len(template.task_templates),
    }
