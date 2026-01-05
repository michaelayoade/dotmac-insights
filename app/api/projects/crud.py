"""
Crud Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from decimal import Decimal

from app.database import get_db
from app.auth import Require, Principal, get_current_principal
from app.models import (
    Project,
    ProjectStatus,
    ProjectPriority,
)
from app.services.projects import (
    ProjectService,
    ProjectCreateData,
    ProjectUpdateData,
    ProjectUserData,
)
from app.services.projects.errors import ProjectNotFoundError
from app.api.projects.projects import get_project, _serialize_project_detail
from app.api.projects.schemas import ProjectCreate, ProjectUpdate

router = APIRouter()


# =============================================================================
# HELPERS
# =============================================================================


def _decimal_or_default(val: Optional[Decimal], default: Decimal = Decimal("0")) -> Decimal:
    """Convert optional decimal to decimal with default."""
    if val is None:
        return default
    return val


# =============================================================================
# PROJECTS CRUD
# =============================================================================


def _convert_users(users: Optional[List]) -> Optional[List[ProjectUserData]]:
    """Convert payload users to ProjectUserData."""
    if users is None:
        return None
    return [
        ProjectUserData(
            user=u.user,
            full_name=u.full_name,
            email=u.email,
            project_status=u.project_status,
            view_attachments=u.view_attachments if u.view_attachments is not None else True,
            welcome_email_sent=u.welcome_email_sent if u.welcome_email_sent is not None else False,
            idx=getattr(u, "idx", None),
        )
        for u in users
    ]


@router.post("/projects", dependencies=[Depends(Require("projects:write"))])
async def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new project with optional team members."""
    service = ProjectService(db, principal)

    data = ProjectCreateData(
        project_name=payload.project_name,
        project_type=payload.project_type,
        status=payload.status or ProjectStatus.OPEN,
        priority=payload.priority or ProjectPriority.MEDIUM,
        department=payload.department,
        company=payload.company,
        cost_center=payload.cost_center,
        customer_account_id=payload.customer_account_id,
        project_manager_id=payload.project_manager_id,
        erpnext_customer=payload.erpnext_customer,
        erpnext_sales_order=payload.erpnext_sales_order,
        percent_complete=Decimal(str(payload.percent_complete)) if payload.percent_complete else None,
        percent_complete_method=payload.percent_complete_method,
        is_active=payload.is_active or "Yes",
        actual_time=Decimal(str(payload.actual_time)) if payload.actual_time else None,
        total_consumed_material_cost=Decimal(str(payload.total_consumed_material_cost)) if payload.total_consumed_material_cost else None,
        estimated_costing=Decimal(str(payload.estimated_costing)) if payload.estimated_costing else None,
        total_costing_amount=Decimal(str(payload.total_costing_amount)) if payload.total_costing_amount else None,
        total_expense_claim=Decimal(str(payload.total_expense_claim)) if payload.total_expense_claim else None,
        total_purchase_cost=Decimal(str(payload.total_purchase_cost)) if payload.total_purchase_cost else None,
        total_sales_amount=Decimal(str(payload.total_sales_amount)) if payload.total_sales_amount else None,
        total_billable_amount=Decimal(str(payload.total_billable_amount)) if payload.total_billable_amount else None,
        total_billed_amount=Decimal(str(payload.total_billed_amount)) if payload.total_billed_amount else None,
        gross_margin=Decimal(str(payload.gross_margin)) if payload.gross_margin else None,
        per_gross_margin=Decimal(str(payload.per_gross_margin)) if payload.per_gross_margin else None,
        collect_progress=bool(payload.collect_progress) if payload.collect_progress is not None else False,
        frequency=payload.frequency,
        message=payload.message,
        notes=payload.notes,
        expected_start_date=payload.expected_start_date,
        expected_end_date=payload.expected_end_date,
        actual_start_date=payload.actual_start_date,
        actual_end_date=payload.actual_end_date,
        from_time=payload.from_time,
        to_time=payload.to_time,
        users=_convert_users(payload.users),
    )

    project = service.create_project(data)
    db.commit()

    # Emit notification via service
    service.emit_project_created_notification(project)

    # Return project detail
    customer = service.get_customer_info(project)
    manager = service.get_manager_info(project)
    task_stats = service.get_project_task_stats(project.id)
    return _serialize_project_detail(project, customer, manager, task_stats)


@router.patch("/projects/{project_id}", dependencies=[Depends(Require("projects:write"))])
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a project and optionally replace team members."""
    service = ProjectService(db, principal)

    try:
        data = ProjectUpdateData(
            project_name=payload.project_name,
            project_type=payload.project_type,
            status=payload.status,
            priority=payload.priority,
            department=payload.department,
            company=payload.company,
            cost_center=payload.cost_center,
            customer_account_id=payload.customer_account_id,
            project_manager_id=payload.project_manager_id,
            erpnext_customer=payload.erpnext_customer,
            erpnext_sales_order=payload.erpnext_sales_order,
            percent_complete=Decimal(str(payload.percent_complete)) if payload.percent_complete is not None else None,
            percent_complete_method=payload.percent_complete_method,
            is_active=payload.is_active,
            actual_time=Decimal(str(payload.actual_time)) if payload.actual_time is not None else None,
            total_consumed_material_cost=Decimal(str(payload.total_consumed_material_cost)) if payload.total_consumed_material_cost is not None else None,
            estimated_costing=Decimal(str(payload.estimated_costing)) if payload.estimated_costing is not None else None,
            total_costing_amount=Decimal(str(payload.total_costing_amount)) if payload.total_costing_amount is not None else None,
            total_expense_claim=Decimal(str(payload.total_expense_claim)) if payload.total_expense_claim is not None else None,
            total_purchase_cost=Decimal(str(payload.total_purchase_cost)) if payload.total_purchase_cost is not None else None,
            total_sales_amount=Decimal(str(payload.total_sales_amount)) if payload.total_sales_amount is not None else None,
            total_billable_amount=Decimal(str(payload.total_billable_amount)) if payload.total_billable_amount is not None else None,
            total_billed_amount=Decimal(str(payload.total_billed_amount)) if payload.total_billed_amount is not None else None,
            gross_margin=Decimal(str(payload.gross_margin)) if payload.gross_margin is not None else None,
            per_gross_margin=Decimal(str(payload.per_gross_margin)) if payload.per_gross_margin is not None else None,
            collect_progress=bool(payload.collect_progress) if payload.collect_progress is not None else None,
            frequency=payload.frequency,
            message=payload.message,
            notes=payload.notes,
            expected_start_date=payload.expected_start_date,
            expected_end_date=payload.expected_end_date,
            actual_start_date=payload.actual_start_date,
            actual_end_date=payload.actual_end_date,
            from_time=payload.from_time,
            to_time=payload.to_time,
            users=_convert_users(payload.users),
        )

        project = service.update_project(project_id, data)
        db.commit()

        # Return project detail
        customer = service.get_customer_info(project)
        manager = service.get_manager_info(project)
        task_stats = service.get_project_task_stats(project.id)
        return _serialize_project_detail(project, customer, manager, task_stats)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.delete("/projects/{project_id}", dependencies=[Depends(Require("projects:write"))])
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Soft-delete a project."""
    service = ProjectService(db, principal)

    try:
        service.delete_project(project_id)
        db.commit()
        return {"message": "Project deleted", "id": project_id}
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
