"""
Workflow Tasks Routes - Unified Task Management with SSR + HTMX.

Permission Requirements:
- tasks:read - View assigned tasks
- tasks:write - Update task status
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.workflow_task import (
    WorkflowTask,
    WorkflowTaskStatus,
    WorkflowTaskPriority,
    WorkflowTaskModule,
)
from app.core.security import is_htmx_request, htmx_toast

# Permission dependencies
RequireTasksRead = Depends(require_scope("tasks:read"))
RequireTasksWrite = Depends(require_scope("tasks:write"))

router = APIRouter(prefix="/tasks", tags=["workflow-tasks"])
templates = get_template_env()


def get_status_options():
    """Get status options for filter dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in WorkflowTaskStatus
    ]


def get_priority_options():
    """Get priority options for filter dropdown."""
    return [
        {"value": p.value, "label": p.value.title()}
        for p in WorkflowTaskPriority
    ]


def get_module_options():
    """Get module options for filter dropdown."""
    return [
        {"value": m.value, "label": m.value.title()}
        for m in WorkflowTaskModule
    ]


def get_task_stats(db, user_id: Optional[int] = None) -> dict:
    """Calculate task statistics."""
    base_query = db.query(func.count(WorkflowTask.id))

    if user_id:
        base_query = base_query.filter(WorkflowTask.assignee_user_id == user_id)

    total_count = base_query.scalar() or 0

    pending_count = base_query.filter(
        WorkflowTask.status == WorkflowTaskStatus.PENDING.value
    ).scalar() or 0

    in_progress_count = db.query(func.count(WorkflowTask.id)).filter(
        WorkflowTask.status == WorkflowTaskStatus.IN_PROGRESS.value
    )
    if user_id:
        in_progress_count = in_progress_count.filter(WorkflowTask.assignee_user_id == user_id)
    in_progress_count = in_progress_count.scalar() or 0

    completed_count = db.query(func.count(WorkflowTask.id)).filter(
        WorkflowTask.status == WorkflowTaskStatus.COMPLETED.value
    )
    if user_id:
        completed_count = completed_count.filter(WorkflowTask.assignee_user_id == user_id)
    completed_count = completed_count.scalar() or 0

    # Overdue count
    overdue_count = db.query(func.count(WorkflowTask.id)).filter(
        WorkflowTask.status == WorkflowTaskStatus.PENDING.value,
        WorkflowTask.due_at < datetime.utcnow(),
        WorkflowTask.due_at.isnot(None),
    )
    if user_id:
        overdue_count = overdue_count.filter(WorkflowTask.assignee_user_id == user_id)
    overdue_count = overdue_count.scalar() or 0

    return {
        "total_count": total_count,
        "pending_count": pending_count,
        "in_progress_count": in_progress_count,
        "completed_count": completed_count,
        "overdue_count": overdue_count,
    }


@router.get("", response_class=HTMLResponse, dependencies=[RequireTasksRead])
async def tasks_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    module: Optional[str] = Query(None, description="Filter by module"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Workflow tasks list page - shows tasks assigned to current user."""
    # Build query - by default show tasks assigned to current user
    query = db.query(WorkflowTask)

    # For now, show all tasks (in production, filter by user.id)
    # query = query.filter(WorkflowTask.assignee_user_id == user.id)

    # Search
    if q:
        search_filter = or_(
            WorkflowTask.title.ilike(f"%{q}%"),
            WorkflowTask.description.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(WorkflowTask.status == status)
    if module:
        query = query.filter(WorkflowTask.module == module)
    if priority:
        query = query.filter(WorkflowTask.priority == priority)

    # Count total
    total = query.count()

    # Sort - pending first, then by due date, then by priority
    query = query.order_by(
        WorkflowTask.due_at.asc().nullslast(),
        WorkflowTask.created_at.desc()
    )

    # Paginate
    offset = (page - 1) * per_page
    tasks = query.offset(offset).limit(per_page).all()

    # Get stats
    stats = get_task_stats(db)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["tasks"] = tasks
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_module"] = module
    context["current_priority"] = priority
    context["status_options"] = get_status_options()
    context["module_options"] = get_module_options()
    context["priority_options"] = get_priority_options()
    context["stats"] = stats
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/workflow_tasks/templates/partials/tasks_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "My Tasks"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Tasks"},
    ])

    template = templates.get_template("modules/workflow_tasks/templates/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireTasksRead])
async def tasks_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Tasks table partial for HTMX updates."""
    return await tasks_list(
        request, response, user, csrf_token, db,
        q, status, module, priority, page, per_page
    )


@router.post("/{task_id}/start", response_class=HTMLResponse, dependencies=[RequireTasksWrite])
async def start_task(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    task_id: int,
):
    """Mark a task as in progress."""
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != WorkflowTaskStatus.PENDING.value:
        htmx_toast(response, "Task is not pending", "error")
    else:
        task.status = WorkflowTaskStatus.IN_PROGRESS.value
        db.commit()
        htmx_toast(response, "Task started", "success")

    # Return updated row
    context = get_base_context(request, response, user, csrf_token)
    context["task"] = task

    template = templates.get_template("modules/workflow_tasks/templates/partials/task_row.html")
    return HTMLResponse(template.render(context))


@router.post("/{task_id}/complete", response_class=HTMLResponse, dependencies=[RequireTasksWrite])
async def complete_task(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    task_id: int,
):
    """Mark a task as completed."""
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == WorkflowTaskStatus.COMPLETED.value:
        htmx_toast(response, "Task is already completed", "info")
    else:
        task.status = WorkflowTaskStatus.COMPLETED.value
        task.completed_at = datetime.utcnow()
        # task.completed_by_id = user.id  # In production
        db.commit()
        htmx_toast(response, "Task completed", "success")

    # Return updated row
    context = get_base_context(request, response, user, csrf_token)
    context["task"] = task

    template = templates.get_template("modules/workflow_tasks/templates/partials/task_row.html")
    return HTMLResponse(template.render(context))


@router.post("/{task_id}/cancel", response_class=HTMLResponse, dependencies=[RequireTasksWrite])
async def cancel_task(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    task_id: int,
):
    """Cancel a task."""
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in [WorkflowTaskStatus.COMPLETED.value, WorkflowTaskStatus.CANCELLED.value]:
        htmx_toast(response, "Cannot cancel this task", "error")
    else:
        task.status = WorkflowTaskStatus.CANCELLED.value
        db.commit()
        htmx_toast(response, "Task cancelled", "success")

    # Return updated row
    context = get_base_context(request, response, user, csrf_token)
    context["task"] = task

    template = templates.get_template("modules/workflow_tasks/templates/partials/task_row.html")
    return HTMLResponse(template.render(context))
