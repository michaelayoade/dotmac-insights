"""
Projects Routes - Project Management with SSR + HTMX.

Permission Requirements:
- projects:read - View projects and project details
- projects:write - Create, update, delete projects
"""
from __future__ import annotations

from typing import Optional, Any
from datetime import datetime

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.project import ProjectStatus, ProjectPriority, ProjectType, MilestoneStatus
from app.models.task import TaskStatus, TaskPriority
from app.core.security import is_htmx_request, htmx_toast, set_flash
from datetime import timedelta
from app.services.projects import (
    ProjectService,
    TaskService,
    MilestoneService,
    ProjectsAnalyticsService,
    ProjectsLookupService,
    ProjectFilters,
    ProjectCreateData,
    ProjectUpdateData,
    TaskFilters,
    TaskCreateData,
    TaskUpdateData,
    MilestoneFilters,
    MilestoneCreateData,
    MilestoneUpdateData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError

# Permission dependencies
RequireProjectsRead = Depends(require_scope("projects:read"))
RequireProjectsWrite = Depends(require_scope("projects:write"))

router = APIRouter(prefix="/projects", tags=["projects"])
dashboard_router = APIRouter(prefix="/projects", tags=["projects-dashboard"])
tasks_router = APIRouter(prefix="/projects", tags=["projects-tasks"])
milestones_router = APIRouter(prefix="/projects", tags=["projects-milestones"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _form_int(form: Any, key: str, default: int) -> int:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    try:
        return int(value) if value not in ("", None) else default
    except (TypeError, ValueError):
        return default


def _form_date(form: Any, key: str) -> Optional[datetime]:
    value = form.get(key)
    if isinstance(value, UploadFile) or not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError:
        return None


def get_status_options():
    """Get status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in ProjectStatus
    ]


def get_priority_options():
    """Get priority options for select dropdown."""
    return [
        {"value": p.value, "label": p.value.title()}
        for p in ProjectPriority
    ]


def get_type_options():
    """Get type options for select dropdown."""
    return [
        {"value": t.value, "label": t.value.title()}
        for t in ProjectType
    ]


@router.get("", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def projects_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("project_name", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Project list page."""
    service = ProjectService(db)

    # Build filters
    status_enum = ProjectStatus(status) if status else None
    priority_enum = ProjectPriority(priority) if priority else None
    filters = ProjectFilters(
        search=q,
        status=status_enum,
        priority=priority_enum,
        sort_by=sort,
        sort_dir=dir,
    )
    pagination = PaginationParams(page=page, limit=per_page)

    result = service.list_projects(filters, pagination)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["projects"] = result.items
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_priority"] = priority
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/projects/templates/partials/projects_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Projects"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Projects"},
    ])

    template = templates.get_template("modules/projects/templates/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def projects_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("project_name"),
    dir: str = Query("asc"),
):
    """Project table partial for HTMX updates."""
    return await projects_list(
        request, response, user, csrf_token, db,
        q, status, priority, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireProjectsWrite])
async def project_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New project form page."""
    lookup = ProjectsLookupService(db)
    customers = lookup.list_customers()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Project"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Projects", "href": "/projects"},
        {"label": "New Project"},
    ])
    context["project"] = None
    context["customers"] = customers
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["type_options"] = get_type_options()
    context["errors"] = {}

    template = templates.get_template("modules/projects/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireProjectsWrite])
async def project_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new project."""
    form = await request.form()

    # Basic validation
    errors = {}
    project_name = _form_str(form, "project_name")

    if not project_name:
        errors["project_name"] = "Project name is required"

    if errors:
        lookup = ProjectsLookupService(db)
        customers = lookup.list_customers()

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Project"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Projects", "href": "/projects"},
            {"label": "New Project"},
        ])
        context["project"] = None
        context["customers"] = customers
        context["status_options"] = get_status_options()
        context["priority_options"] = get_priority_options()
        context["type_options"] = get_type_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/projects/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Parse dates
    expected_start = _form_date(form, "expected_start_date")
    expected_end = _form_date(form, "expected_end_date")

    # Parse status and priority
    status_str = _form_str(form, "status", ProjectStatus.OPEN.value)
    priority_str = _form_str(form, "priority", ProjectPriority.MEDIUM.value)

    # Create project using service
    service = ProjectService(db)
    data = ProjectCreateData(
        project_name=project_name,
        project_type=_form_str(form, "project_type") or None,
        status=ProjectStatus(status_str),
        priority=ProjectPriority(priority_str),
        department=_form_str(form, "department") or None,
        expected_start_date=expected_start,
        expected_end_date=expected_end,
        notes=_form_str(form, "notes") or None,
        customer_account_id=_form_int(form, "customer_account_id", 0) or None,
    )

    project = service.create_project(data)
    db.commit()

    set_flash(response, f"Project '{project.project_name}' created successfully.", "success")
    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)


@router.get("/{project_id}", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def project_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    project_id: int,
):
    """Project detail page."""
    service = ProjectService(db)
    milestone_service = MilestoneService(db)

    try:
        project = service.get_project(project_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get milestones using service
    milestone_filters = MilestoneFilters()
    milestones_result = milestone_service.list_project_milestones(project_id, milestone_filters)
    milestones = milestones_result.items

    lookup = ProjectsLookupService(db)

    project_manager_info = service.get_manager_info(project)
    project_manager = None
    if project_manager_info:
        project_manager = lookup.get_employee(project_manager_info["id"])

    related_service_orders = lookup.list_related_service_orders(project_id)
    service_order_stats = lookup.get_service_order_stats(project_id)

    related_tickets = lookup.list_related_tickets(project.project_name)
    ticket_stats = lookup.get_ticket_stats(project.project_name)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = project.project_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Projects", "href": "/projects"},
        {"label": project.project_name},
    ])
    context["project"] = project
    context["milestones"] = milestones
    context["project_manager"] = project_manager
    context["related_service_orders"] = related_service_orders
    context["service_order_stats"] = service_order_stats
    context["related_tickets"] = related_tickets
    context["ticket_stats"] = ticket_stats

    template = templates.get_template("modules/projects/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{project_id}/edit", response_class=HTMLResponse, dependencies=[RequireProjectsWrite])
async def project_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    project_id: int,
):
    """Project edit form page."""
    service = ProjectService(db)
    try:
        project = service.get_project(project_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    lookup = ProjectsLookupService(db)
    customers = lookup.list_customers()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {project.project_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Projects", "href": "/projects"},
        {"label": project.project_name, "href": f"/projects/{project.id}"},
        {"label": "Edit"},
    ])
    context["project"] = project
    context["customers"] = customers
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["type_options"] = get_type_options()
    context["errors"] = {}

    template = templates.get_template("modules/projects/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{project_id}", response_class=HTMLResponse, dependencies=[RequireProjectsWrite])
async def project_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    project_id: int,
):
    """Update a project."""
    service = ProjectService(db)
    try:
        project = service.get_project(project_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    form = await request.form()

    # Basic validation
    errors = {}
    project_name = _form_str(form, "project_name")

    if not project_name:
        errors["project_name"] = "Project name is required"

    if errors:
        lookup = ProjectsLookupService(db)
        customers = lookup.list_customers()

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {project.project_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Projects", "href": "/projects"},
            {"label": project.project_name, "href": f"/projects/{project.id}"},
            {"label": "Edit"},
        ])
        context["project"] = project
        context["customers"] = customers
        context["status_options"] = get_status_options()
        context["priority_options"] = get_priority_options()
        context["type_options"] = get_type_options()
        context["errors"] = errors

        template = templates.get_template("modules/projects/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Parse dates
    expected_start = _form_date(form, "expected_start_date")
    expected_end = _form_date(form, "expected_end_date")

    # Parse status and priority
    status_str = _form_str(form, "status", project.status.value if project.status else "")
    priority_str = _form_str(form, "priority", project.priority.value if project.priority else "")

    # Update project using service
    data = ProjectUpdateData(
        project_name=project_name,
        project_type=_form_str(form, "project_type") or None,
        status=ProjectStatus(status_str) if status_str else None,
        priority=ProjectPriority(priority_str) if priority_str else None,
        department=_form_str(form, "department") or None,
        expected_start_date=expected_start,
        expected_end_date=expected_end,
        notes=_form_str(form, "notes") or None,
        customer_account_id=_form_int(form, "customer_account_id", 0) or None,
    )

    project = service.update_project(project_id, data)
    db.commit()

    set_flash(response, f"Project '{project.project_name}' updated successfully.", "success")
    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)


@router.delete("/{project_id}", response_class=HTMLResponse, dependencies=[RequireProjectsWrite])
async def project_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    project_id: int,
):
    """Delete a project (soft delete)."""
    service = ProjectService(db)
    try:
        project = service.delete_project(project_id)
        name = project.project_name
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    if is_htmx_request(request):
        htmx_toast(response, f"Project '{name}' deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Project '{name}' deleted.", "success")
    return RedirectResponse(url="/projects", status_code=303)


@router.get("/{project_id}/row", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def project_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    project_id: int,
):
    """Single project row partial for HTMX updates."""
    service = ProjectService(db)
    try:
        project = service.get_project(project_id)
    except NotFoundError:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["project"] = project

    template = templates.get_template("modules/projects/templates/partials/project_row.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# PROJECTS DASHBOARD
# =============================================================================

@dashboard_router.get("/dashboard", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def projects_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Projects Dashboard with overview stats."""
    # Use service for all dashboard data (single call, optimized queries)
    analytics_service = ProjectsAnalyticsService(db)
    dashboard_data = analytics_service.get_dashboard_data()

    # Map stats to template format
    stats = {
        "total_active": dashboard_data.stats.active_projects,
        "total_completed": dashboard_data.stats.completed_projects,
        "overdue_projects": dashboard_data.stats.overdue_projects,
        "open_tasks": dashboard_data.stats.total_open_tasks,
        "overdue_tasks": dashboard_data.stats.overdue_tasks,
    }

    # Status distribution for chart
    status_distribution = [
        {"status": s.status, "count": s.count}
        for s in dashboard_data.status_distribution
    ]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Projects Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Projects"},
    ])

    context["stats"] = stats
    context["status_distribution"] = status_distribution
    context["recent_projects"] = dashboard_data.recent_projects
    context["upcoming_milestones"] = dashboard_data.upcoming_milestones
    context["overdue_task_list"] = dashboard_data.overdue_tasks
    context["today"] = datetime.utcnow().date()

    template = templates.get_template("modules/projects/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# TASKS MANAGEMENT
# =============================================================================

def get_task_status_options():
    """Get task status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in TaskStatus
    ]


def get_task_priority_options():
    """Get task priority options for select dropdown."""
    return [
        {"value": p.value, "label": p.value.title()}
        for p in TaskPriority
    ]


@tasks_router.get("/tasks", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def tasks_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Tasks list page."""
    task_service = TaskService(db)

    # Build filters
    status_enum = TaskStatus(status) if status else None
    priority_enum = TaskPriority(priority) if priority else None
    filters = TaskFilters(
        search=q,
        status=status_enum,
        priority=priority_enum,
        project_id=project_id,
    )
    pagination = PaginationParams(page=page, limit=per_page)

    result = task_service.list_tasks(filters, pagination)

    lookup = ProjectsLookupService(db)
    projects = lookup.list_active_projects()

    today = datetime.utcnow().date()
    stats = task_service.get_status_counts()

    context = get_base_context(request, response, user, csrf_token)
    context["tasks"] = result.items
    context["projects"] = projects
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_priority"] = priority
    context["current_project_id"] = project_id
    context["status_options"] = get_task_status_options()
    context["priority_options"] = get_task_priority_options()
    context["pagination"] = build_pagination_context(page, per_page, result.total)
    context["today"] = today

    if is_htmx_request(request):
        template = templates.get_template("modules/projects/templates/partials/tasks_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Tasks"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Projects", "href": "/projects"},
        {"label": "Tasks"},
    ])

    template = templates.get_template("modules/projects/templates/pages/tasks_list.html")
    return HTMLResponse(template.render(context))


@tasks_router.get("/tasks/{task_id}", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def task_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    task_id: int,
):
    """Task detail page."""
    task_service = TaskService(db)

    try:
        task = task_service.get_task(task_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get sub-tasks
    sub_tasks = task_service.get_sub_tasks(task_id)

    # Get dependencies
    dependencies = task.depends_on

    # Load assigned employee
    assigned_employee = None
    if task.assigned_to_id:
        lookup = ProjectsLookupService(db)
        assigned_employee = lookup.get_employee(task.assigned_to_id)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = task.subject
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Projects", "href": "/projects"},
        {"label": "Tasks", "href": "/projects/tasks"},
        {"label": task.subject[:30] + "..." if len(task.subject) > 30 else task.subject},
    ])
    context["task"] = task
    context["sub_tasks"] = sub_tasks
    context["dependencies"] = dependencies
    context["assigned_employee"] = assigned_employee
    context["status_options"] = get_task_status_options()
    context["priority_options"] = get_task_priority_options()

    template = templates.get_template("modules/projects/templates/pages/task_detail.html")
    return HTMLResponse(template.render(context))


@tasks_router.post("/tasks/{task_id}/status", response_class=HTMLResponse, dependencies=[RequireProjectsWrite])
async def task_update_status(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    task_id: int,
):
    """Quick task status update via HTMX."""
    task_service = TaskService(db)

    try:
        task = task_service.get_task(task_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")

    form = await request.form()
    new_status = _form_str(form, "status")

    if new_status:
        data = TaskUpdateData(status=TaskStatus(new_status))
        task = task_service.update_task(task_id, data)
        db.commit()

        htmx_toast(response, f"Task status updated to {new_status.replace('_', ' ').title()}", "success")

    # Return updated task row
    context = get_base_context(request, response, user, "")
    context["task"] = task
    context["today"] = datetime.utcnow().date()

    template = templates.get_template("modules/projects/templates/partials/task_row.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))


# =============================================================================
# MILESTONES MANAGEMENT
# =============================================================================

def get_milestone_status_options():
    """Get milestone status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in MilestoneStatus
    ]


@milestones_router.get("/milestones", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def milestones_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Milestones list page."""
    milestone_service = MilestoneService(db)

    status_enum = MilestoneStatus(status) if status else None
    filters = MilestoneFilters(
        search=q,
        status=status_enum,
        project_id=project_id,
        sort_by="planned_end_date",
        sort_dir="asc",
    )
    pagination = PaginationParams(page=page, limit=per_page)

    result = milestone_service.list_milestones(filters, pagination)
    milestones = result.items

    lookup = ProjectsLookupService(db)
    projects = lookup.list_active_projects()

    today = datetime.utcnow().date()
    stats = milestone_service.get_status_counts()

    context = get_base_context(request, response, user, csrf_token)
    context["milestones"] = milestones
    context["projects"] = projects
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_project_id"] = project_id
    context["status_options"] = get_milestone_status_options()
    context["pagination"] = build_pagination_context(page, per_page, result.total)
    context["today"] = today

    if is_htmx_request(request):
        template = templates.get_template("modules/projects/templates/partials/milestones_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Milestones"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Projects", "href": "/projects"},
        {"label": "Milestones"},
    ])

    template = templates.get_template("modules/projects/templates/pages/milestones_list.html")
    return HTMLResponse(template.render(context))


@milestones_router.get("/milestones/{milestone_id}", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def milestone_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    milestone_id: int,
):
    """Milestone detail page."""
    milestone_service = MilestoneService(db)

    try:
        milestone, tasks = milestone_service.get_milestone_with_tasks(milestone_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Milestone not found")

    # Calculate progress using service
    progress_data = milestone_service.calculate_progress(milestone_id)
    total_tasks = progress_data.total_tasks
    completed_tasks = progress_data.completed_tasks
    progress = float(progress_data.percent_complete)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = milestone.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Projects", "href": "/projects"},
        {"label": "Milestones", "href": "/projects/milestones"},
        {"label": milestone.name},
    ])
    context["milestone"] = milestone
    context["tasks"] = tasks
    context["total_tasks"] = total_tasks
    context["completed_tasks"] = completed_tasks
    context["progress"] = progress
    context["today"] = datetime.utcnow().date()

    template = templates.get_template("modules/projects/templates/pages/milestone_detail.html")
    return HTMLResponse(template.render(context))


@milestones_router.post("/milestones/{milestone_id}/status", response_class=HTMLResponse, dependencies=[RequireProjectsWrite])
async def milestone_update_status(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    milestone_id: int,
):
    """Quick milestone status update via HTMX."""
    milestone_service = MilestoneService(db)

    try:
        milestone = milestone_service.get_milestone(milestone_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Milestone not found")

    form = await request.form()
    new_status = _form_str(form, "status")

    if new_status:
        milestone = milestone_service.update_milestone(
            milestone_id, MilestoneUpdateData(status=MilestoneStatus(new_status))
        )
        db.commit()

        htmx_toast(response, f"Milestone status updated to {new_status.replace('_', ' ').title()}", "success")

    # Return updated row
    context = get_base_context(request, response, user, "")
    context["milestone"] = milestone
    context["today"] = datetime.utcnow().date()

    template = templates.get_template("modules/projects/templates/partials/milestone_row.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))
