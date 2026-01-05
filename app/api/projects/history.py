"""
History Endpoints
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
from app.services.audit_logger import AuditLogger

router = APIRouter()

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
    entity: Project | Task | Milestone | None
    if entity_type == "project":
        entity = db.query(Project).filter(Project.id == entity_id, Project.is_deleted == False).first()
    elif entity_type == "task":
        entity = db.query(Task).filter(Task.id == entity_id).first()
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
    history.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)

    # Apply limit after merge
    history = history[:limit]

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "total": len(history),
        "data": history,
    }
