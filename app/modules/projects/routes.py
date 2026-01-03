"""
Projects Routes - Project Management with SSR + HTMX.

Permission Requirements:
- projects:read - View projects and project details
- projects:write - Create, update, delete projects
"""
from __future__ import annotations

from typing import Optional, Any
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.project import Project, ProjectStatus, ProjectPriority, ProjectType, Milestone, MilestoneStatus
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.party import CustomerAccount, Party
from app.models.employee import Employee
from app.core.security import is_htmx_request, htmx_toast, set_flash
from datetime import timedelta

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
    query = db.query(Project).filter(Project.is_deleted == False)

    # Search
    if q:
        search_filter = or_(
            Project.project_name.ilike(f"%{q}%"),
            Project.project_type.ilike(f"%{q}%"),
            Project.department.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(Project.status == status)
    if priority:
        query = query.filter(Project.priority == priority)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(Project, sort, Project.project_name)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    projects = query.offset(offset).limit(per_page).all()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["projects"] = projects
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_priority"] = priority
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

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
    # Get customer accounts for dropdown
    customers = (
        db.query(CustomerAccount)
        .join(Party, CustomerAccount.party_id == Party.id)
        .order_by(Party.name)
        .limit(100)
        .all()
    )

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
        customers = (
            db.query(CustomerAccount)
            .join(Party, CustomerAccount.party_id == Party.id)
            .order_by(Party.name)
            .limit(100)
            .all()
        )

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

    # Create project
    project = Project(
        project_name=project_name,
        project_type=_form_str(form, "project_type") or None,
        status=_form_str(form, "status", ProjectStatus.OPEN.value),
        priority=_form_str(form, "priority", ProjectPriority.MEDIUM.value),
        department=_form_str(form, "department") or None,
        expected_start_date=expected_start,
        expected_end_date=expected_end,
        notes=_form_str(form, "notes") or None,
    )

    # Link customer account if provided
    customer_account_id = _form_int(form, "customer_account_id", 0)
    if customer_account_id:
        project.customer_account_id = customer_account_id

    db.add(project)
    db.commit()
    db.refresh(project)

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
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.is_deleted == False,
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get milestones
    milestones = db.query(Milestone).filter(
        Milestone.project_id == project_id,
        Milestone.is_deleted == False,
    ).order_by(Milestone.idx).all()

    # Load project manager
    from app.models.employee import Employee
    project_manager = None
    if project.project_manager_id:
        project_manager = db.query(Employee).filter(
            Employee.id == project.project_manager_id
        ).first()

    # Load related service orders
    from app.models.field_service import ServiceOrder
    related_service_orders = db.query(ServiceOrder).filter(
        ServiceOrder.project_id == project_id,
    ).order_by(ServiceOrder.created_at.desc()).limit(10).all()

    service_order_stats = {
        "total": db.query(func.count(ServiceOrder.id)).filter(
            ServiceOrder.project_id == project_id,
        ).scalar() or 0,
    }

    # Load related tickets
    from app.models.unified_ticket import UnifiedTicket
    related_tickets = db.query(UnifiedTicket).filter(
        UnifiedTicket.project_name == project.project_name,
        UnifiedTicket.is_deleted == False,
    ).order_by(UnifiedTicket.created_at.desc()).limit(10).all()

    ticket_stats = {
        "total": db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.project_name == project.project_name,
            UnifiedTicket.is_deleted == False,
        ).scalar() or 0,
        "open": db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.project_name == project.project_name,
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.status.in_(["open", "in_progress"]),
        ).scalar() or 0,
    }

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
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.is_deleted == False,
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    customers = (
        db.query(CustomerAccount)
        .join(Party, CustomerAccount.party_id == Party.id)
        .order_by(Party.name)
        .limit(100)
        .all()
    )

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
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.is_deleted == False,
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    form = await request.form()

    # Basic validation
    errors = {}
    project_name = _form_str(form, "project_name")

    if not project_name:
        errors["project_name"] = "Project name is required"

    if errors:
        customers = (
            db.query(CustomerAccount)
            .join(Party, CustomerAccount.party_id == Party.id)
            .order_by(Party.name)
            .limit(100)
            .all()
        )

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

    # Update project
    project.project_name = project_name
    project.project_type = _form_str(form, "project_type") or None
    status_str = _form_str(form, "status", project.status.value if project.status else "")
    if status_str:
        project.status = ProjectStatus(status_str)
    priority_str = _form_str(form, "priority", project.priority.value if project.priority else "")
    if priority_str:
        project.priority = ProjectPriority(priority_str)
    project.department = _form_str(form, "department") or None
    project.expected_start_date = expected_start
    project.expected_end_date = expected_end
    project.notes = _form_str(form, "notes") or None

    # Link customer account if provided
    customer_account_id = _form_int(form, "customer_account_id", 0)
    project.customer_account_id = customer_account_id or None

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
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.is_deleted == False,
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    name = project.project_name
    project.is_deleted = True
    project.deleted_at = datetime.utcnow()
    db.commit()

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
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.is_deleted == False,
    ).first()

    if not project:
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
    today = datetime.utcnow().date()
    week_from_now = today + timedelta(days=7)

    # Project Stats
    total_active = db.query(func.count(Project.id)).filter(
        Project.is_deleted == False,
        Project.status.in_(["open", "working", "in_progress"])
    ).scalar() or 0

    total_completed = db.query(func.count(Project.id)).filter(
        Project.is_deleted == False,
        Project.status == "completed"
    ).scalar() or 0

    overdue_projects = db.query(func.count(Project.id)).filter(
        Project.is_deleted == False,
        Project.expected_end_date < today,
        Project.status.notin_(["completed", "cancelled"])
    ).scalar() or 0

    # Task Stats
    open_tasks = db.query(func.count(Task.id)).filter(
        Task.status.in_(["open", "working", "pending_review"])
    ).scalar() or 0

    overdue_tasks = db.query(func.count(Task.id)).filter(
        Task.exp_end_date < today,
        Task.status.notin_(["completed", "cancelled"])
    ).scalar() or 0

    # Projects by status
    status_counts = db.query(
        Project.status,
        func.count(Project.id).label("count")
    ).filter(Project.is_deleted == False).group_by(Project.status).all()

    status_distribution = [
        {"status": s[0], "count": s[1]}
        for s in status_counts
    ]

    # Recent projects
    recent_projects = db.query(Project).filter(
        Project.is_deleted == False
    ).order_by(Project.updated_at.desc()).limit(10).all()

    # Upcoming milestones
    upcoming_milestones = db.query(Milestone).filter(
        Milestone.is_deleted == False,
        Milestone.planned_end_date >= today,
        Milestone.planned_end_date <= week_from_now,
        Milestone.status != MilestoneStatus.COMPLETED
    ).order_by(Milestone.planned_end_date).limit(5).all()

    # Overdue tasks
    overdue_task_list = db.query(Task).filter(
        Task.exp_end_date < today,
        Task.status.notin_(["completed", "cancelled"])
    ).order_by(Task.exp_end_date).limit(5).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Projects Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Projects"},
    ])

    context["stats"] = {
        "total_active": total_active,
        "total_completed": total_completed,
        "overdue_projects": overdue_projects,
        "open_tasks": open_tasks,
        "overdue_tasks": overdue_tasks,
    }
    context["status_distribution"] = status_distribution
    context["recent_projects"] = recent_projects
    context["upcoming_milestones"] = upcoming_milestones
    context["overdue_task_list"] = overdue_task_list
    context["today"] = today

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
    query = db.query(Task)

    # Search
    if q:
        query = query.filter(
            or_(
                Task.subject.ilike(f"%{q}%"),
                Task.description.ilike(f"%{q}%"),
            )
        )

    # Filters
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if project_id:
        query = query.filter(Task.project_id == project_id)

    # Count total
    total = query.count()

    # Sort
    query = query.order_by(Task.exp_end_date.asc().nullslast(), Task.priority.desc())

    # Paginate
    offset = (page - 1) * per_page
    tasks = query.offset(offset).limit(per_page).all()

    # Get projects for filter
    projects = db.query(Project).filter(
        Project.is_deleted == False,
        Project.status.notin_(["completed", "cancelled"])
    ).order_by(Project.project_name).all()

    # Stats
    today = datetime.utcnow().date()
    stats = {
        "open": db.query(func.count(Task.id)).filter(Task.status == TaskStatus.OPEN).scalar() or 0,
        "working": db.query(func.count(Task.id)).filter(Task.status == TaskStatus.WORKING).scalar() or 0,
        "overdue": db.query(func.count(Task.id)).filter(
            Task.exp_end_date < today,
            Task.status.notin_(["completed", "cancelled"])
        ).scalar() or 0,
        "completed": db.query(func.count(Task.id)).filter(Task.status == TaskStatus.COMPLETED).scalar() or 0,
    }

    context = get_base_context(request, response, user, csrf_token)
    context["tasks"] = tasks
    context["projects"] = projects
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_priority"] = priority
    context["current_project_id"] = project_id
    context["status_options"] = get_task_status_options()
    context["priority_options"] = get_task_priority_options()
    context["pagination"] = build_pagination_context(page, per_page, total)
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
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get sub-tasks
    sub_tasks = db.query(Task).filter(Task.parent_task_id == task_id).all()

    # Get dependencies
    dependencies = task.depends_on

    # Load assigned employee
    from app.models.employee import Employee
    assigned_employee = None
    if task.assigned_to_id:
        assigned_employee = db.query(Employee).filter(
            Employee.id == task.assigned_to_id
        ).first()

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
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    form = await request.form()
    new_status = _form_str(form, "status")

    if new_status:
        task.status = TaskStatus(new_status)
        if new_status == "completed":
            task.completed_on = datetime.utcnow().date()
            task.progress = Decimal("100")
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
    query = db.query(Milestone).filter(Milestone.is_deleted == False)

    # Search
    if q:
        query = query.filter(
            or_(
                Milestone.name.ilike(f"%{q}%"),
                Milestone.description.ilike(f"%{q}%"),
            )
        )

    # Filters
    if status:
        query = query.filter(Milestone.status == status)
    if project_id:
        query = query.filter(Milestone.project_id == project_id)

    # Count total
    total = query.count()

    # Sort
    query = query.order_by(Milestone.planned_end_date.asc().nullslast())

    # Paginate
    offset = (page - 1) * per_page
    milestones = query.offset(offset).limit(per_page).all()

    # Get projects for filter
    projects = db.query(Project).filter(
        Project.is_deleted == False,
        Project.status.notin_(["completed", "cancelled"])
    ).order_by(Project.project_name).all()

    # Stats
    today = datetime.utcnow().date()
    stats = {
        "pending": db.query(func.count(Milestone.id)).filter(
            Milestone.is_deleted == False,
            Milestone.status == MilestoneStatus.PLANNED
        ).scalar() or 0,
        "in_progress": db.query(func.count(Milestone.id)).filter(
            Milestone.is_deleted == False,
            Milestone.status == MilestoneStatus.IN_PROGRESS
        ).scalar() or 0,
        "overdue": db.query(func.count(Milestone.id)).filter(
            Milestone.is_deleted == False,
            Milestone.planned_end_date < today,
            Milestone.status != MilestoneStatus.COMPLETED
        ).scalar() or 0,
        "completed": db.query(func.count(Milestone.id)).filter(
            Milestone.is_deleted == False,
            Milestone.status == MilestoneStatus.COMPLETED
        ).scalar() or 0,
    }

    context = get_base_context(request, response, user, csrf_token)
    context["milestones"] = milestones
    context["projects"] = projects
    context["stats"] = stats
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_project_id"] = project_id
    context["status_options"] = get_milestone_status_options()
    context["pagination"] = build_pagination_context(page, per_page, total)
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
    milestone = db.query(Milestone).filter(
        Milestone.id == milestone_id,
        Milestone.is_deleted == False
    ).first()

    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    # Get tasks linked to this milestone
    tasks = db.query(Task).filter(Task.milestone_id == milestone_id).all()

    # Calculate progress
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
    progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

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
    milestone = db.query(Milestone).filter(
        Milestone.id == milestone_id,
        Milestone.is_deleted == False
    ).first()

    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    form = await request.form()
    new_status = _form_str(form, "status")

    if new_status:
        milestone.status = MilestoneStatus(new_status)
        db.commit()

        htmx_toast(response, f"Milestone status updated to {new_status.replace('_', ' ').title()}", "success")

    # Return updated row
    context = get_base_context(request, response, user, "")
    context["milestone"] = milestone
    context["today"] = datetime.utcnow().date()

    template = templates.get_template("modules/projects/templates/partials/milestone_row.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))
