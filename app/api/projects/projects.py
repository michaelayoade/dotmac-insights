"""
Projects Endpoints
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
from app.models.party import CustomerAccount
from app.models.employee import Employee

router = APIRouter()

# =============================================================================
# PROJECTS LIST & DETAIL
# =============================================================================

@router.get("/projects", dependencies=[Depends(Require("explorer:read"))])
async def list_projects(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    customer_account_id: Optional[int] = None,
    project_type: Optional[str] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    overdue_only: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
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

    if customer_account_id:
        query = query.filter(Project.customer_account_id == customer_account_id)

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
            Project.expected_end_date < datetime.now(timezone.utc),
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
                "customer_account_id": p.customer_account_id,
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
    if project.customer_account_id:
        account = db.query(CustomerAccount).filter(CustomerAccount.id == project.customer_account_id).first()
        if account and account.party:
            customer = {
                "id": account.id,
                "party_id": account.party_id,
                "name": account.party.name,
                "email": account.party.primary_email,
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
        "percent_complete": float(project.percent_complete) if project.percent_complete else 0,
        "gross_margin": float(project.gross_margin) if project.gross_margin else 0,
        "total_sales_amount": float(project.total_sales_amount) if project.total_sales_amount else 0,
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

