"""
Projects Gantt & Enhanced Features Routes - SSR + HTMX

Provides web routes for:
- Gantt chart visualization
- Comments on projects/tasks/milestones
- Attachments management
- Activity log
"""
from ._deps import (
    # FastAPI
    APIRouter, Request, Response, Query, HTTPException,
    HTMLResponse, RedirectResponse,
    # Types
    Optional, datetime,
    # Context helpers
    get_base_context, build_breadcrumbs,
    # Dependencies
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireProjectsRead, RequireProjectsWrite,
    PaginationParams,
    # Templates
    templates,
    # Models
    Project,
    # Helpers
    is_htmx_request, htmx_toast, set_flash,
    _form_str,
    # Service
    ProjectsWebService,
)
import json

router = APIRouter(tags=["projects-gantt"])  # Prefix added in __init__.py


# =============================================================================
# GANTT CHART VIEW
# =============================================================================

@router.get("/{project_id}/gantt", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def project_gantt(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    project_id: int,
):
    """Display Gantt chart for a project."""
    service = ProjectsWebService(db, user_id=user.id, principal=user)
    gantt_data = service.get_gantt_data(project_id)

    if not gantt_data:
        set_flash(response, "Project not found", "error")
        return RedirectResponse("/projects", status_code=303)

    project_info = gantt_data["project"]

    context = {
        **get_base_context(request, response, user, csrf_token),
        "page_title": f"Gantt Chart - {project_info['name']}",
        "breadcrumbs": build_breadcrumbs([
            {"label": "Projects", "url": "/projects"},
            {"label": project_info["name"], "url": f"/projects/{project_id}"},
            {"label": "Gantt Chart"},
        ]),
        "project_id": project_id,
        "project_name": project_info["name"],
        "gantt_data": gantt_data,
        "gantt_json": json.dumps(gantt_data),
    }

    template = templates.get_template("modules/projects/templates/pages/gantt.html")
    return HTMLResponse(template.render(context))


@router.get("/gantt", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def gantt_index(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Gantt landing page - redirect to first project or show empty state."""
    service = ProjectsWebService(db, user_id=user.id, principal=user)
    result = service.project_service.list_projects(
        pagination=PaginationParams(offset=0, limit=1),
    )
    if result.items:
        return RedirectResponse(url=f"/projects/{result.items[0].id}/gantt", status_code=302)

    empty_gantt = {
        "project": {"id": 0, "name": "Projects"},
        "tasks": [],
        "milestones": [],
        "date_range": {"min_date": None, "max_date": None},
    }

    context = {
        **get_base_context(request, response, user, csrf_token),
        "page_title": "Gantt Chart",
        "breadcrumbs": build_breadcrumbs([
            {"label": "Projects", "url": "/projects"},
            {"label": "Gantt Chart"},
        ]),
        "project_id": 0,
        "project_name": "No projects available",
        "gantt_data": empty_gantt,
        "gantt_json": json.dumps(empty_gantt),
    }

    template = templates.get_template("modules/projects/templates/pages/gantt.html")
    return HTMLResponse(template.render(context))


@router.get("/{project_id}/gantt-data", dependencies=[RequireProjectsRead])
async def project_gantt_data(
    request: Request,
    user: SessionUser,
    db: DB,
    project_id: int,
):
    """Return Gantt data as JSON for HTMX/JS consumption."""
    service = ProjectsWebService(db, user_id=user.id, principal=user)
    gantt_data = service.get_gantt_data(project_id)

    if not gantt_data:
        raise HTTPException(status_code=404, detail="Project not found")

    from fastapi.responses import JSONResponse
    return JSONResponse(content=gantt_data)


# =============================================================================
# COMMENTS
# =============================================================================

@router.get("/{entity_type}/{entity_id}/comments", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def entity_comments(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    entity_type: str,
    entity_id: int,
):
    """List comments for a project, task, or milestone."""
    if entity_type not in ("project", "task", "milestone"):
        raise HTTPException(status_code=400, detail="Invalid entity type")

    service = ProjectsWebService(db, user_id=user.id, principal=user)
    result = service.list_comments(entity_type, entity_id)

    context = {
        **get_base_context(request, response, user, csrf_token),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "comments": result["items"],
        "total_comments": result["total"],
    }

    template = templates.get_template("modules/projects/templates/partials/comments.html")
    return HTMLResponse(template.render(context))


@router.post("/{entity_type}/{entity_id}/comments", response_class=HTMLResponse, dependencies=[RequireProjectsWrite])
async def create_comment(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    _csrf: CSRFProtect,
    db: DB,
    entity_type: str,
    entity_id: int,
):
    """Create a new comment."""
    if entity_type not in ("project", "task", "milestone"):
        raise HTTPException(status_code=400, detail="Invalid entity type")

    form = await request.form()
    content = _form_str(form, "content")

    if not content:
        htmx_toast(response, "Comment cannot be empty", "error")
        return Response(status_code=204)

    service = ProjectsWebService(db, user_id=user.id, principal=user)
    service.create_comment(
        entity_type=entity_type,
        entity_id=entity_id,
        content=content,
    )

    # Return updated comments list
    result = service.list_comments(entity_type, entity_id)

    context = {
        **get_base_context(request, response, user, csrf_token),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "comments": result["items"],
        "total_comments": result["total"],
    }

    htmx_toast(response, "Comment added", "success")
    template = templates.get_template("modules/projects/templates/partials/comments.html")
    return HTMLResponse(template.render(context))


@router.delete("/{entity_type}/{entity_id}/comments/{comment_id}", dependencies=[RequireProjectsWrite])
async def delete_comment(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    _csrf: CSRFProtect,
    db: DB,
    entity_type: str,
    entity_id: int,
    comment_id: int,
):
    """Delete a comment."""
    service = ProjectsWebService(db, user_id=user.id, principal=user)
    success = service.delete_comment(comment_id)

    if success:
        htmx_toast(response, "Comment deleted", "success")
    else:
        htmx_toast(response, "Comment not found", "error")

    # Return updated comments list
    result = service.list_comments(entity_type, entity_id)

    context = {
        **get_base_context(request, response, user, csrf_token),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "comments": result["items"],
        "total_comments": result["total"],
    }

    template = templates.get_template("modules/projects/templates/partials/comments.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# ATTACHMENTS
# =============================================================================

@router.get("/{entity_type}/{entity_id}/attachments", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def entity_attachments(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    entity_type: str,
    entity_id: int,
):
    """List attachments for a project or task."""
    if entity_type not in ("project", "task"):
        raise HTTPException(status_code=400, detail="Invalid entity type")

    service = ProjectsWebService(db, user_id=user.id, principal=user)
    attachments = service.list_attachments(entity_type, entity_id)

    context = {
        **get_base_context(request, response, user, csrf_token),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "attachments": attachments,
    }

    template = templates.get_template("modules/projects/templates/partials/attachments.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# ACTIVITY LOG
# =============================================================================

@router.get("/{project_id}/activity", response_class=HTMLResponse, dependencies=[RequireProjectsRead])
async def project_activity(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    project_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List activity log for a project."""
    service = ProjectsWebService(db, user_id=user.id, principal=user)
    activities = service.list_activity(project_id, limit, offset)

    context = {
        **get_base_context(request, response, user, csrf_token),
        "project_id": project_id,
        "activities": activities,
        "activity_limit": limit,
        "activity_offset": offset,
    }

    template = templates.get_template("modules/projects/templates/partials/activity_log.html")
    return HTMLResponse(template.render(context))
