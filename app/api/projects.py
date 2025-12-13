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
from pydantic import BaseModel, Field
from decimal import Decimal

from app.database import get_db
from app.models.project import Project, ProjectStatus, ProjectPriority, ProjectUser
from app.models.task import Task, TaskStatus, TaskPriority, TaskDependency
from app.models.expense import Expense
from app.models.customer import Customer
from app.models.employee import Employee
from app.auth import Require
from app.cache import cached, CACHE_TTL

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
    project_name: Optional[str] = None  # Allow changing the name


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
    subject: Optional[str] = None  # Allow updating subject


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
                "name": emp.employee_name,
                "email": emp.company_email,
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
        for u in sorted(project.users, key=lambda x: x.idx)
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
# PROJECTS CRUD
# =============================================================================


def _decimal_or_default(val: Optional[Decimal], default: Decimal = Decimal("0")) -> Decimal:
    return Decimal(str(val)) if val is not None else default


@router.post("/projects", dependencies=[Depends(Require("projects:write"))])
async def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
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
