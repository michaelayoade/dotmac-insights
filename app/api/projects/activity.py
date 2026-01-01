"""
Activity Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc, asc, false
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
from app.api.projects.comments import VALID_ENTITY_TYPES

router = APIRouter()

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
    offset: int = Query(default=0, ge=0),
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
    task_clause = (
        and_(ProjectActivity.entity_type == "task", ProjectActivity.entity_id.in_(task_ids))
        if task_ids
        else false()
    )
    milestone_clause = (
        and_(ProjectActivity.entity_type == "milestone", ProjectActivity.entity_id.in_(milestone_ids))
        if milestone_ids
        else false()
    )
    query = db.query(ProjectActivity).filter(
        or_(
            and_(ProjectActivity.entity_type == "project", ProjectActivity.entity_id == project_id),
            task_clause,
            milestone_clause,
        )
    )

    activities = query.order_by(ProjectActivity.created_at.desc()).limit(limit).all()

    return {
        "project_id": project_id,
        "total": len(activities),
        "data": [_serialize_activity(a) for a in activities],
    }

