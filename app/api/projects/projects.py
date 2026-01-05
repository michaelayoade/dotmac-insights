"""
Projects Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, Principal, get_current_principal
from app.cache import cached, CACHE_TTL
from app.models import (
    Project,
    ProjectStatus,
    ProjectPriority,
    Task,
    TaskStatus,
)
from app.services.projects import (
    ProjectService,
    ProjectFilters,
)
from app.services.projects.errors import ProjectNotFoundError
from app.services.types import PaginationParams

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
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """List projects with filtering and pagination."""
    # Parse status and priority enums
    status_enum = None
    priority_enum = None

    if status:
        try:
            status_enum = ProjectStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if priority:
        try:
            priority_enum = ProjectPriority(priority)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    # Build filters
    filters = ProjectFilters(
        status=status_enum,
        priority=priority_enum,
        customer_account_id=customer_account_id,
        project_type=project_type,
        department=department,
        search=search,
        overdue_only=overdue_only,
        start_date=datetime.fromisoformat(start_date) if start_date else None,
        end_date=datetime.fromisoformat(end_date) if end_date else None,
    )
    pagination = PaginationParams(limit=limit, offset=offset)

    # Use service
    service = ProjectService(db, principal)
    result = service.list_projects(filters, pagination)

    return {
        "total": result.total,
        "limit": result.limit,
        "offset": result.offset,
        "data": [_serialize_project_list(p) for p in result.items],
    }


def _serialize_project_list(p: Project) -> Dict[str, Any]:
    """Serialize a project for list view."""
    return {
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


@router.get("/projects/{project_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Get detailed project information with all child tables."""
    service = ProjectService(db, principal)

    try:
        project = service.get_project(project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    # Use service methods to get related info
    customer = service.get_customer_info(project)
    manager = service.get_manager_info(project)
    task_stats = service.get_project_task_stats(project_id)

    return _serialize_project_detail(project, customer, manager, task_stats)


def _serialize_project_detail(
    project: Project,
    customer: Optional[Dict[str, Any]],
    manager: Optional[Dict[str, Any]],
    task_stats,
) -> Dict[str, Any]:
    """Serialize a project for detail view."""
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
        "task_stats": {
            "total": task_stats.total,
            "completed": task_stats.completed,
            "open": task_stats.open,
            "overdue": task_stats.overdue,
        },
        "expenses": expenses,
        "write_back_status": getattr(project, "write_back_status", None),
    }

