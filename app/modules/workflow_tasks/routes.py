"""
Workflow Tasks Routes - Unified Task Management with SSR + HTMX.

Permission Requirements:
- tasks:read - View assigned tasks
- tasks:write - Update task status
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.workflow_task import (
    WorkflowTaskStatus,
    WorkflowTaskPriority,
    WorkflowTaskModule,
)
from app.core.security import is_htmx_request, htmx_toast
from app.services.workflow_task_service import WorkflowTaskService

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
    service = WorkflowTaskService(db)
    offset = (page - 1) * per_page

    # Get tasks for current user using service
    tasks = service.get_my_tasks(
        user_id=user.id,
        status=status,
        module=module,
        priority=priority,
        search=q,
        limit=per_page,
        offset=offset,
    )

    # Get total count for pagination
    total = service.count_my_tasks(
        user_id=user.id,
        status=status,
        module=module,
        priority=priority,
        search=q,
    )

    # Get stats using service
    summary = service.get_task_summary(user.id)
    stats = {
        "pending_count": summary.get("pending", 0),
        "overdue_count": summary.get("overdue", 0),
        "in_progress_count": summary.get("by_priority", {}).get("in_progress", 0),
        "completed_count": summary.get("completed_today", 0),
        "total_count": summary.get("pending", 0) + summary.get("due_today", 0),
    }

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
    service = WorkflowTaskService(db)

    # Get task with ownership check
    task = service.get_task_by_id(task_id, user_id=user.id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != WorkflowTaskStatus.PENDING.value:
        htmx_toast(response, "Task is not pending", "error")
    else:
        task = service.update_task_status(task_id, WorkflowTaskStatus.IN_PROGRESS.value, user.id)
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
    service = WorkflowTaskService(db)

    # Get task with ownership check
    task = service.get_task_by_id(task_id, user_id=user.id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == WorkflowTaskStatus.COMPLETED.value:
        htmx_toast(response, "Task is already completed", "info")
    else:
        task = service.update_task_status(task_id, WorkflowTaskStatus.COMPLETED.value, user.id)
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
    service = WorkflowTaskService(db)

    # Get task with ownership check
    task = service.get_task_by_id(task_id, user_id=user.id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in [WorkflowTaskStatus.COMPLETED.value, WorkflowTaskStatus.CANCELLED.value]:
        htmx_toast(response, "Cannot cancel this task", "error")
    else:
        task = service.update_task_status(task_id, WorkflowTaskStatus.CANCELLED.value, user.id)
        db.commit()
        htmx_toast(response, "Task cancelled", "success")

    # Return updated row
    context = get_base_context(request, response, user, csrf_token)
    context["task"] = task

    template = templates.get_template("modules/workflow_tasks/templates/partials/task_row.html")
    return HTMLResponse(template.render(context))
