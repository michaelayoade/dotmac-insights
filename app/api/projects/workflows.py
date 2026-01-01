"""
Workflows Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc, asc
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import Require, get_current_user
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
from app.models.notification import NotificationEventType
from app.services.notification_service import NotificationService
from app.api.projects.schemas import _log_activity

router = APIRouter()

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
    payload: Optional[ApprovalSubmitPayload] = None,
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
            current_step = engine._get_current_step(approval)
            approver_ids = engine._get_step_approver_ids(current_step) if current_step else []
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
    payload: Optional[ApprovalActionPayload] = None,
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
