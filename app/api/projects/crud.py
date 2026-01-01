"""
Crud Endpoints
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
from app.models.auth import User
from app.models.notification import NotificationEventType
from app.services.notification_service import NotificationService
from app.api.projects.projects import get_project
from app.api.projects.schemas import ProjectCreate, ProjectUpdate

router = APIRouter()

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
    project.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Project deleted", "id": project_id}
