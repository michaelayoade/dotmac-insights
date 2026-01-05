"""
Milestones Endpoints
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
from app.models.auth import User
from app.auth import get_current_user
from app.api.projects.crud import _decimal_or_default
from app.api.projects.schemas import MilestoneCreate, MilestoneUpdate

router = APIRouter()

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
    milestone.deleted_at = datetime.now(timezone.utc)
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
