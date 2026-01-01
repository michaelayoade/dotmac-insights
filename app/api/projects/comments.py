"""
Comments Endpoints
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
from app.auth import get_current_user
from app.api.projects.schemas import CommentCreate, CommentUpdate

router = APIRouter()

# =============================================================================
# COMMENTS
# =============================================================================

VALID_ENTITY_TYPES = {"project", "task", "milestone"}


def _serialize_comment(comment: ProjectComment) -> Dict[str, Any]:
    """Serialize a comment to a dictionary."""
    return {
        "id": comment.id,
        "entity_type": comment.entity_type,
        "entity_id": comment.entity_id,
        "content": comment.content,
        "author_id": comment.author_id,
        "author_name": comment.author_name,
        "author_email": comment.author_email,
        "is_edited": comment.is_edited,
        "edited_at": comment.edited_at.isoformat() if comment.edited_at else None,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


@router.get("/projects/{entity_type}/{entity_id}/comments", dependencies=[Depends(Require("explorer:read"))])
async def list_entity_comments(
    entity_type: str,
    entity_id: int,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all comments for an entity (project, task, or milestone)."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    query = db.query(ProjectComment).filter(
        ProjectComment.entity_type == entity_type,
        ProjectComment.entity_id == entity_id,
        ProjectComment.is_deleted == False,
    )

    total = query.count()
    comments = query.order_by(ProjectComment.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_comment(c) for c in comments],
    }


@router.post("/projects/{entity_type}/{entity_id}/comments", dependencies=[Depends(Require("projects:write"))])
async def create_comment(
    entity_type: str,
    entity_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new comment on an entity."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")

    # Verify entity exists
    entity: object | None = None
    company: Optional[str] = None
    if entity_type == "project":
        entity = db.query(Project).filter(Project.id == entity_id, Project.is_deleted == False).first()
    elif entity_type == "task":
        entity = db.query(Task).filter(Task.id == entity_id).first()
    elif entity_type == "milestone":
        entity = db.query(Milestone).filter(Milestone.id == entity_id, Milestone.is_deleted == False).first()
    else:
        entity = None
        company = None

    if entity:
        company = getattr(entity, "company", None)

    if not entity:
        raise HTTPException(status_code=404, detail=f"{entity_type.capitalize()} not found")

    comment = ProjectComment(
        entity_type=entity_type,
        entity_id=entity_id,
        content=payload.content,
        author_id=current_user.id,
        author_name=current_user.name,
        author_email=current_user.email,
        company=company,
    )

    db.add(comment)

    # Create activity record
    activity = ProjectActivity(
        entity_type=entity_type,
        entity_id=entity_id,
        activity_type=ProjectActivityType.COMMENT_ADDED,
        description=f"Comment added by {current_user.name or current_user.email}",
        actor_id=current_user.id,
        actor_name=current_user.name,
        actor_email=current_user.email,
        company=company,
    )
    db.add(activity)

    db.commit()
    db.refresh(comment)

    return _serialize_comment(comment)


@router.patch("/projects/comments/{comment_id}", dependencies=[Depends(Require("projects:write"))])
async def update_comment(
    comment_id: int,
    payload: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update a comment (only the author can edit)."""
    comment = db.query(ProjectComment).filter(
        ProjectComment.id == comment_id,
        ProjectComment.is_deleted == False,
    ).first()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Only author can edit
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the author can edit this comment")

    comment.content = payload.content
    comment.is_edited = True
    comment.edited_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(comment)

    return _serialize_comment(comment)


@router.delete("/projects/comments/{comment_id}", dependencies=[Depends(Require("projects:write"))])
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Soft-delete a comment (author or admin can delete)."""
    comment = db.query(ProjectComment).filter(
        ProjectComment.id == comment_id,
        ProjectComment.is_deleted == False,
    ).first()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    comment.is_deleted = True
    comment.deleted_at = datetime.now(timezone.utc)
    comment.deleted_by_id = current_user.id
    db.commit()

    return {"message": "Comment deleted", "id": comment_id}

