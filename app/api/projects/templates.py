"""
Templates Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc, asc
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

from app.database import get_db
from app.auth import Require, Principal, get_current_principal
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
from app.api.projects.schemas import _log_activity

router = APIRouter()

# =============================================================================
# PROJECT TEMPLATES
# =============================================================================


class TaskTemplatePayload(BaseModel):
    """Task template payload."""
    subject: str
    description: Optional[str] = None
    priority: Optional[str] = None
    start_day_offset: int = 0
    duration_days: int = 1
    default_assigned_role: Optional[str] = None
    is_group: bool = False
    idx: int = 0


class MilestoneTemplatePayload(BaseModel):
    """Milestone template payload."""
    name: str
    description: Optional[str] = None
    start_day_offset: int = 0
    end_day_offset: int = 7
    idx: int = 0


class ProjectTemplateCreate(BaseModel):
    """Create project template payload."""
    name: str
    description: Optional[str] = None
    project_type: Optional[str] = None
    default_priority: Optional[ProjectPriority] = None
    estimated_duration_days: Optional[int] = None
    default_notes: Optional[str] = None
    is_active: Optional[bool] = None
    task_templates: Optional[List[TaskTemplatePayload]] = Field(default=None, alias="tasks")
    milestone_templates: Optional[List[MilestoneTemplatePayload]] = Field(default=None, alias="milestones")

    model_config = ConfigDict(populate_by_name=True)


class ProjectTemplateUpdate(BaseModel):
    """Update project template payload."""
    name: Optional[str] = None
    description: Optional[str] = None
    project_type: Optional[str] = None
    default_priority: Optional[ProjectPriority] = None
    estimated_duration_days: Optional[int] = None
    default_notes: Optional[str] = None
    is_active: Optional[bool] = None
    task_templates: Optional[List[TaskTemplatePayload]] = Field(default=None, alias="tasks")
    milestone_templates: Optional[List[MilestoneTemplatePayload]] = Field(default=None, alias="milestones")

    model_config = ConfigDict(populate_by_name=True)


def _validate_task_template_priority(priority: Optional[str]) -> Optional[str]:
    """Validate task template priority values to avoid invalid enums later."""
    if priority is None:
        return None
    try:
        TaskPriority(priority)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid task template priority: {priority}")
    return priority


def _serialize_template(template: ProjectTemplate) -> Dict[str, Any]:
    """Serialize project template to dict."""
    task_templates = [
        {
            "id": t.id,
            "subject": t.subject,
            "description": t.description,
            "priority": t.priority,
            "start_day_offset": t.start_day_offset,
            "duration_days": t.duration_days,
            "default_assigned_role": t.default_assigned_role,
            "is_group": t.is_group,
            "idx": t.idx,
        }
        for t in sorted(template.task_templates, key=lambda x: x.idx)
    ]
    milestone_templates = [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "start_day_offset": m.start_day_offset,
            "end_day_offset": m.end_day_offset,
            "idx": m.idx,
        }
        for m in sorted(template.milestone_templates, key=lambda x: x.idx)
    ]
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "project_type": template.project_type,
        "default_priority": template.default_priority.value if template.default_priority else None,
        "estimated_duration_days": template.estimated_duration_days,
        "default_notes": template.default_notes,
        "is_active": template.is_active,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "task_count": len(template.task_templates),
        "milestone_count": len(template.milestone_templates),
        "task_templates": task_templates,
        "milestone_templates": milestone_templates,
        "tasks": task_templates,
        "milestones": milestone_templates,
    }


@router.get("/projects/templates", dependencies=[Depends(Require("explorer:read"))])
async def list_project_templates(
    active_only: bool = Query(default=True),
    is_active: Optional[bool] = Query(default=None),
    project_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all project templates."""
    query = db.query(ProjectTemplate)

    if is_active is not None:
        query = query.filter(ProjectTemplate.is_active == is_active)
    elif active_only:
        query = query.filter(ProjectTemplate.is_active == True)

    if project_type:
        query = query.filter(ProjectTemplate.project_type == project_type)

    total = query.count()
    templates = query.order_by(ProjectTemplate.name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [_serialize_template(t) for t in templates],
    }


@router.post("/projects/templates", dependencies=[Depends(Require("projects:admin"))])
async def create_project_template(
    payload: ProjectTemplateCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new project template."""
    template = ProjectTemplate(
        name=payload.name,
        description=payload.description,
        project_type=payload.project_type,
        default_priority=payload.default_priority,
        estimated_duration_days=payload.estimated_duration_days,
        default_notes=payload.default_notes,
        is_active=payload.is_active if payload.is_active is not None else True,
        created_by_id=principal.id,
    )
    db.add(template)
    db.flush()

    # Add task templates
    if payload.task_templates:
        for idx, tt in enumerate(payload.task_templates):
            task_template = TaskTemplate(
                project_template_id=template.id,
                subject=tt.subject,
                description=tt.description,
                priority=_validate_task_template_priority(tt.priority),
                start_day_offset=tt.start_day_offset,
                duration_days=tt.duration_days,
                default_assigned_role=tt.default_assigned_role,
                is_group=tt.is_group,
                idx=tt.idx or idx,
            )
            db.add(task_template)

    # Add milestone templates
    if payload.milestone_templates:
        for idx, mt in enumerate(payload.milestone_templates):
            milestone_template = MilestoneTemplate(
                project_template_id=template.id,
                name=mt.name,
                description=mt.description,
                start_day_offset=mt.start_day_offset,
                end_day_offset=mt.end_day_offset,
                idx=mt.idx or idx,
            )
            db.add(milestone_template)

    db.commit()
    db.refresh(template)

    return {
        "message": "Template created",
        "id": template.id,
        "template": _serialize_template(template),
    }


@router.get("/projects/templates/{template_id}", dependencies=[Depends(Require("explorer:read"))])
async def get_project_template(
    template_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a project template by ID."""
    template = db.query(ProjectTemplate).filter(ProjectTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return _serialize_template(template)


@router.patch("/projects/templates/{template_id}", dependencies=[Depends(Require("projects:admin"))])
async def update_project_template(
    template_id: int,
    payload: ProjectTemplateUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Update a project template."""
    template = db.query(ProjectTemplate).filter(ProjectTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Update fields
    if payload.name is not None:
        template.name = payload.name
    if payload.description is not None:
        template.description = payload.description
    if payload.project_type is not None:
        template.project_type = payload.project_type
    if payload.default_priority is not None:
        template.default_priority = payload.default_priority
    if payload.estimated_duration_days is not None:
        template.estimated_duration_days = payload.estimated_duration_days
    if payload.default_notes is not None:
        template.default_notes = payload.default_notes
    if payload.is_active is not None:
        template.is_active = payload.is_active
    if payload.task_templates is not None:
        template.task_templates.clear()
        for idx, tt in enumerate(payload.task_templates):
            task_template = TaskTemplate(
                project_template_id=template.id,
                subject=tt.subject,
                description=tt.description,
                priority=_validate_task_template_priority(tt.priority),
                start_day_offset=tt.start_day_offset,
                duration_days=tt.duration_days,
                default_assigned_role=tt.default_assigned_role,
                is_group=tt.is_group,
                idx=tt.idx or idx,
            )
            db.add(task_template)
    if payload.milestone_templates is not None:
        template.milestone_templates.clear()
        for idx, mt in enumerate(payload.milestone_templates):
            milestone_template = MilestoneTemplate(
                project_template_id=template.id,
                name=mt.name,
                description=mt.description,
                start_day_offset=mt.start_day_offset,
                end_day_offset=mt.end_day_offset,
                idx=mt.idx or idx,
            )
            db.add(milestone_template)

    db.commit()
    db.refresh(template)

    return {
        "message": "Template updated",
        "template": _serialize_template(template),
    }


@router.delete("/projects/templates/{template_id}", dependencies=[Depends(Require("projects:admin"))])
async def delete_project_template(
    template_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Delete a project template."""
    template = db.query(ProjectTemplate).filter(ProjectTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    db.delete(template)
    db.commit()

    return {"message": "Template deleted", "id": template_id}


class CreateFromTemplatePayload(BaseModel):
    """Payload for creating a project from a template."""
    project_name: str
    expected_start_date: Optional[date] = None
    customer_id: Optional[int] = None
    project_manager_id: Optional[int] = None
    notes: Optional[str] = None


@router.post("/projects/from-template/{template_id}", dependencies=[Depends(Require("projects:write"))])
async def create_project_from_template(
    template_id: int,
    payload: CreateFromTemplatePayload,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    """Create a new project from a template."""
    template = db.query(ProjectTemplate).filter(
        ProjectTemplate.id == template_id,
        ProjectTemplate.is_active == True,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found or inactive")

    # Calculate dates
    start_date = payload.expected_start_date or date.today()
    end_date = None
    if template.estimated_duration_days:
        end_date = start_date + timedelta(days=template.estimated_duration_days)

    # Create project
    project = Project(
        project_name=payload.project_name,
        project_type=template.project_type,
        priority=template.default_priority,
        status=ProjectStatus.OPEN,
        expected_start_date=start_date,
        expected_end_date=end_date,
        notes=payload.notes or template.default_notes,
        customer_id=payload.customer_id,
        project_manager_id=payload.project_manager_id,
    )
    db.add(project)
    db.flush()

    # Create milestones from template
    milestone_map = {}  # template_id -> created_milestone
    for mt in sorted(template.milestone_templates, key=lambda x: x.idx):
        milestone = Milestone(
            project_id=project.id,
            name=mt.name,
            description=mt.description,
            status=MilestoneStatus.PLANNED,
            planned_start_date=start_date + timedelta(days=mt.start_day_offset),
            planned_end_date=start_date + timedelta(days=mt.end_day_offset),
            idx=mt.idx,
            created_by_id=principal.id,
        )
        db.add(milestone)
        db.flush()
        milestone_map[mt.id] = milestone

    # Create tasks from template
    for tt in sorted(template.task_templates, key=lambda x: x.idx):
        task_priority = TaskPriority.MEDIUM
        if tt.priority:
            try:
                task_priority = TaskPriority(tt.priority)
            except ValueError:
                task_priority = TaskPriority.MEDIUM
        milestone_for_task = (
            milestone_map.get(tt.milestone_template_id)
            if tt.milestone_template_id and tt.milestone_template_id in milestone_map
            else None
        )
        task = Task(
            project_id=project.id,
            subject=tt.subject,
            description=tt.description,
            priority=task_priority,
            status=TaskStatus.OPEN,
            exp_start_date=start_date + timedelta(days=tt.start_day_offset),
            exp_end_date=start_date + timedelta(days=tt.start_day_offset + tt.duration_days),
            is_group=tt.is_group,
            milestone_id=milestone_for_task.id if milestone_for_task else None,
        )
        db.add(task)

    # Log activity
    _log_activity(
        db=db,
        entity_type="project",
        entity_id=project.id,
        activity_type=ProjectActivityType.CREATED,
        description=f"Project created from template: {template.name}",
        actor_id=principal.id,
        actor_name=user.name if hasattr(user, "name") else None,
        actor_email=user.email if hasattr(user, "email") else None,
    )

    db.commit()
    db.refresh(project)

    return {
        "message": "Project created from template",
        "project_id": project.id,
        "project_name": project.project_name,
        "template_id": template_id,
        "milestones_created": len(milestone_map),
        "tasks_created": len(template.task_templates),
    }
