"""API endpoints for unified workflow tasks."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_principal, Principal, require_auth
from app.services.workflow_task_service import WorkflowTaskService
from app.services.scheduled_task_service import ScheduledTaskService
from app.models.workflow_task import WorkflowTask, WorkflowTaskStatus

router = APIRouter(prefix="/workflow-tasks", tags=["Workflow Tasks"])


# =============================================================================
# SCHEMAS
# =============================================================================

class WorkflowTaskResponse(BaseModel):
    """Response schema for workflow task."""

    id: int
    source_type: str
    source_id: int
    title: str
    description: Optional[str] = None
    action_url: Optional[str] = None
    assignee_user_id: Optional[int] = None
    assignee_employee_id: Optional[int] = None
    assignee_team_id: Optional[int] = None
    assignee_display_name: Optional[str] = None
    assigned_at: datetime
    priority: str
    due_at: Optional[datetime] = None
    status: str
    completed_at: Optional[datetime] = None
    module: str
    company: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_overdue: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskSummaryResponse(BaseModel):
    """Response schema for task summary."""

    pending: int
    overdue: int
    due_today: int
    completed_today: int
    by_module: Dict[str, int]
    by_priority: Dict[str, int]


class TaskListResponse(BaseModel):
    """Response schema for task list."""

    items: List[WorkflowTaskResponse]
    total: int
    limit: int
    offset: int


class UpdateTaskStatusRequest(BaseModel):
    """Request schema for updating task status."""

    status: str = Field(..., description="New status: pending, in_progress, completed, cancelled")


class SnoozeTaskRequest(BaseModel):
    """Request schema for snoozing a task."""

    snooze_until: datetime = Field(..., description="New due date/time")


class ScheduleReminderRequest(BaseModel):
    """Request schema for scheduling a reminder."""

    entity_type: str = Field(..., description="Type of entity (lead, ticket, etc.)")
    entity_id: int = Field(..., description="ID of the entity")
    remind_at: datetime = Field(..., description="When to send the reminder")
    message: str = Field(..., description="Reminder message")
    title: Optional[str] = Field(None, description="Optional notification title")


class ScheduledTaskResponse(BaseModel):
    """Response schema for scheduled task."""

    id: int
    celery_task_id: str
    task_name: str
    scheduled_for: datetime
    executed_at: Optional[datetime] = None
    status: str
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# WORKFLOW TASK ENDPOINTS
# =============================================================================

@router.get("/my-tasks", response_model=TaskListResponse)
async def get_my_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    module: Optional[str] = Query(None, description="Filter by module"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    overdue_only: bool = Query(False, description="Only show overdue tasks"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Dict[str, Any]:
    """
    Get unified task list for current user.

    Returns tasks from all modules (approvals, tickets, expenses, etc.)
    assigned to the current user.
    """
    require_auth(principal)

    service = WorkflowTaskService(db)
    tasks = service.get_my_tasks(
        user_id=principal.id,
        status=status,
        module=module,
        priority=priority,
        overdue_only=overdue_only,
        limit=limit,
        offset=offset,
    )
    total = service.count_my_tasks(
        user_id=principal.id,
        status=status,
        module=module,
        priority=priority,
        overdue_only=overdue_only,
    )

    # Convert to response format
    items = []
    for task in tasks:
        item = WorkflowTaskResponse.model_validate(task)
        item.is_overdue = task.is_overdue
        item.assignee_display_name = task.assignee_display_name
        items.append(item)

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/my-tasks/summary", response_model=TaskSummaryResponse)
async def get_my_tasks_summary(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Dict[str, Any]:
    """
    Get task counts by module and status for current user.

    Useful for dashboard widgets showing pending task counts.
    """
    require_auth(principal)

    service = WorkflowTaskService(db)
    return service.get_task_summary(user_id=principal.id)


@router.get("/{task_id}", response_model=WorkflowTaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> WorkflowTaskResponse:
    """Get a specific workflow task."""
    require_auth(principal)

    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check authorization (user can only see their own tasks unless superuser)
    if not principal.is_superuser and task.assignee_user_id != principal.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this task")

    response = WorkflowTaskResponse.model_validate(task)
    response.is_overdue = task.is_overdue
    response.assignee_display_name = task.assignee_display_name
    return response


@router.post("/{task_id}/complete", response_model=WorkflowTaskResponse)
async def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> WorkflowTaskResponse:
    """Mark a task as completed."""
    require_auth(principal)

    service = WorkflowTaskService(db)
    task = service.update_task_status(
        task_id=task_id,
        status=WorkflowTaskStatus.COMPLETED.value,
        user_id=principal.id,
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check authorization
    if not principal.is_superuser and task.assignee_user_id != principal.id:
        db.rollback()
        raise HTTPException(status_code=403, detail="Not authorized to complete this task")

    db.commit()

    response = WorkflowTaskResponse.model_validate(task)
    response.is_overdue = task.is_overdue
    response.assignee_display_name = task.assignee_display_name
    return response


@router.post("/{task_id}/snooze", response_model=WorkflowTaskResponse)
async def snooze_task(
    task_id: int,
    request: SnoozeTaskRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> WorkflowTaskResponse:
    """Snooze a task by updating its due date."""
    require_auth(principal)

    service = WorkflowTaskService(db)
    task = service.snooze_task(
        task_id=task_id,
        new_due_at=request.snooze_until,
        user_id=principal.id,
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check authorization
    if not principal.is_superuser and task.assignee_user_id != principal.id:
        db.rollback()
        raise HTTPException(status_code=403, detail="Not authorized to snooze this task")

    db.commit()

    response = WorkflowTaskResponse.model_validate(task)
    response.is_overdue = task.is_overdue
    response.assignee_display_name = task.assignee_display_name
    return response


@router.patch("/{task_id}/status", response_model=WorkflowTaskResponse)
async def update_task_status(
    task_id: int,
    request: UpdateTaskStatusRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> WorkflowTaskResponse:
    """Update a task's status."""
    require_auth(principal)

    # Validate status
    valid_statuses = [s.value for s in WorkflowTaskStatus]
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    service = WorkflowTaskService(db)
    task = service.update_task_status(
        task_id=task_id,
        status=request.status,
        user_id=principal.id,
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check authorization
    if not principal.is_superuser and task.assignee_user_id != principal.id:
        db.rollback()
        raise HTTPException(status_code=403, detail="Not authorized to update this task")

    db.commit()

    response = WorkflowTaskResponse.model_validate(task)
    response.is_overdue = task.is_overdue
    response.assignee_display_name = task.assignee_display_name
    return response


# =============================================================================
# SCHEDULED TASK ENDPOINTS
# =============================================================================

@router.post("/schedule-reminder", response_model=ScheduledTaskResponse)
async def schedule_reminder(
    request: ScheduleReminderRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> ScheduledTaskResponse:
    """
    Schedule a reminder for a specific entity.

    The reminder will be sent as an in-app notification at the specified time.
    """
    require_auth(principal)

    from app.tasks.scheduled_actions import send_reminder

    # Validate remind_at is in the future
    if request.remind_at <= datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="Reminder time must be in the future",
        )

    service = ScheduledTaskService(db)
    scheduled = service.schedule(
        task=send_reminder,
        eta=request.remind_at,
        kwargs={
            "entity_type": request.entity_type,
            "entity_id": request.entity_id,
            "user_id": principal.id,
            "message": request.message,
            "title": request.title,
        },
        source_type=request.entity_type,
        source_id=request.entity_id,
        created_by_id=principal.id,
    )

    db.commit()
    return ScheduledTaskResponse.model_validate(scheduled)


@router.get("/scheduled", response_model=List[ScheduledTaskResponse])
async def list_scheduled_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> List[ScheduledTaskResponse]:
    """List scheduled tasks."""
    require_auth(principal)

    service = ScheduledTaskService(db)

    if source_type and source_id:
        created_by_id = None if principal.is_superuser else principal.id
        tasks = service.get_pending_for_source(
            source_type,
            source_id,
            created_by_id=created_by_id,
        )
    else:
        created_by_id = None if principal.is_superuser else principal.id
        tasks = service.list_scheduled(
            status=status,
            source_type=source_type,
            created_by_id=created_by_id,
            limit=limit,
            offset=offset,
        )

    return [ScheduledTaskResponse.model_validate(t) for t in tasks]


@router.delete("/scheduled/{scheduled_task_id}")
async def cancel_scheduled_task(
    scheduled_task_id: int,
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Dict[str, Any]:
    """Cancel a scheduled task."""
    require_auth(principal)

    service = ScheduledTaskService(db)
    scheduled_task = service.get_by_id(scheduled_task_id)
    if not scheduled_task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")

    if not principal.is_superuser and scheduled_task.created_by_id != principal.id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this task")

    success = service.cancel(
        scheduled_task_id=scheduled_task_id,
        cancelled_by_id=principal.id,
        reason=reason,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Scheduled task not found or already executed",
        )

    db.commit()
    return {"status": "cancelled", "scheduled_task_id": scheduled_task_id}
