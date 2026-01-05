"""
Tasks Endpoints
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
from app.models.employee import Employee
from app.api.projects.crud import _decimal_or_default
from app.api.projects.schemas import TaskCreate, TaskUpdate

router = APIRouter()

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
    offset: int = Query(default=0, ge=0),
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
        "project_id": task.project_id,
        "assigned_to_id": task.assigned_to_id,
        "completed_by_id": task.completed_by_id,
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
    assigned_to = payload.assigned_to
    completed_by = payload.completed_by
    if payload.assigned_to_id and not assigned_to:
        employee = db.query(Employee).filter(Employee.id == payload.assigned_to_id).first()
        if employee:
            assigned_to = employee.name
    if payload.completed_by_id and not completed_by:
        employee = db.query(Employee).filter(Employee.id == payload.completed_by_id).first()
        if employee:
            completed_by = employee.name

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
        assigned_to=assigned_to,
        completed_by=completed_by,
        assigned_to_id=payload.assigned_to_id,
        completed_by_id=payload.completed_by_id,
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
    if payload.assigned_to_id is not None:
        task.assigned_to_id = payload.assigned_to_id
        if payload.assigned_to is None:
            employee = db.query(Employee).filter(Employee.id == payload.assigned_to_id).first()
            if employee:
                task.assigned_to = employee.name
    if payload.completed_by is not None:
        task.completed_by = payload.completed_by
    if payload.completed_by_id is not None:
        task.completed_by_id = payload.completed_by_id
        if payload.completed_by is None:
            employee = db.query(Employee).filter(Employee.id == payload.completed_by_id).first()
            if employee:
                task.completed_by = employee.name
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
