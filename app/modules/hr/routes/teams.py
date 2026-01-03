"""
HR Teams Routes - Helpdesk Team Management with SSR + HTMX.

Permission Requirements:
- hr:read - View teams and members
- hr:write - Create/update/delete teams and manage members

Uses OrganizationService for all business logic.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import is_htmx_request
from app.services.hr.organization import OrganizationService
from app.services.hr.organization_types import (
    HDTeamFilters,
    HDTeamCreateData,
    HDTeamUpdateData,
    TeamMemberData,
)
from app.services.types import PaginationParams
from app.services.hr.errors import HDTeamNotFoundError

RequireHRRead = Depends(require_scope("hr:read"))
RequireHRWrite = Depends(require_scope("hr:write"))

router = APIRouter(prefix="/teams", tags=["hr-teams"])
templates = get_template_env()

ASSIGNMENT_RULES = [
    ("Round Robin", "Round Robin"),
    ("Load Balancing", "Load Balancing"),
    ("Manual Assignment", "Manual Assignment"),
]


def _form_str(value: Optional[str]) -> Optional[str]:
    """Return None for empty strings."""
    return value.strip() if value and value.strip() else None


def _form_bool(form_data: dict, key: str) -> bool:
    """Parse form checkbox value."""
    return key in form_data


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def teams_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """HD Teams list page."""
    service = OrganizationService(db)
    offset = (page - 1) * per_page

    filters = HDTeamFilters(search=q)
    pagination = PaginationParams(offset=offset, limit=per_page)
    result = service.list_hd_teams(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["teams"] = result.items
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    if is_htmx_request(request):
        template = templates.get_template("modules/hr/templates/teams/partials/teams_table.html")
        return HTMLResponse(template.render(context))

    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "HD Teams"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Teams"},
    ])

    template = templates.get_template("modules/hr/templates/teams/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def teams_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """HTMX table partial."""
    return await teams_list(request, response, user, csrf_token, db, q, page, per_page)


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def team_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New team form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New HD Team"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Teams", "href": "/hr/teams"},
        {"label": "New"},
    ])
    context["team"] = None
    context["form_data"] = None
    context["errors"] = {}
    context["assignment_rules"] = ASSIGNMENT_RULES

    template = templates.get_template("modules/hr/templates/teams/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def team_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: CSRFProtect,
):
    """Create a new team."""
    form_data = await request.form()
    service = OrganizationService(db)

    errors: dict = {}
    name = _form_str(form_data.get("team_name"))
    if not name:
        errors["team_name"] = "Team name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New HD Team"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Teams", "href": "/hr/teams"},
            {"label": "New"},
        ])
        context["team"] = None
        context["form_data"] = dict(form_data)
        context["errors"] = errors
        context["assignment_rules"] = ASSIGNMENT_RULES

        template = templates.get_template("modules/hr/templates/teams/pages/form.html")
        return HTMLResponse(template.render(context))

    create_data = HDTeamCreateData(
        team_name=name,
        description=_form_str(form_data.get("description")),
        assignment_rule=_form_str(form_data.get("assignment_rule")),
        ignore_restrictions=_form_bool(form_data, "ignore_restrictions"),
    )

    team = service.create_hd_team(create_data)
    db.commit()

    return RedirectResponse(
        url=f"/hr/teams/{team.id}",
        status_code=303,
    )


@router.get("/{team_id}", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def team_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    team_id: int,
):
    """Team detail page with members."""
    service = OrganizationService(db)

    try:
        team = service.get_hd_team(team_id)
        members = service.get_team_members(team_id)
    except HDTeamNotFoundError:
        raise HTTPException(status_code=404, detail="Team not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Team - {team.team_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Teams", "href": "/hr/teams"},
        {"label": team.team_name},
    ])
    context["team"] = team
    context["members"] = members

    template = templates.get_template("modules/hr/templates/teams/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{team_id}/edit", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def team_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    team_id: int,
):
    """Edit team form."""
    service = OrganizationService(db)

    try:
        team = service.get_hd_team(team_id)
    except HDTeamNotFoundError:
        raise HTTPException(status_code=404, detail="Team not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit - {team.team_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Teams", "href": "/hr/teams"},
        {"label": team.team_name, "href": f"/hr/teams/{team.id}"},
        {"label": "Edit"},
    ])
    context["team"] = team
    context["form_data"] = None
    context["errors"] = {}
    context["assignment_rules"] = ASSIGNMENT_RULES

    template = templates.get_template("modules/hr/templates/teams/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{team_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def team_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    team_id: int,
    _: CSRFProtect,
):
    """Update a team."""
    form_data = await request.form()
    service = OrganizationService(db)

    try:
        team = service.get_hd_team(team_id)
    except HDTeamNotFoundError:
        raise HTTPException(status_code=404, detail="Team not found")

    errors: dict = {}
    name = _form_str(form_data.get("team_name"))
    if not name:
        errors["team_name"] = "Team name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit - {team.team_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "HR", "href": "/hr/employees"},
            {"label": "Teams", "href": "/hr/teams"},
            {"label": team.team_name, "href": f"/hr/teams/{team.id}"},
            {"label": "Edit"},
        ])
        context["team"] = team
        context["form_data"] = dict(form_data)
        context["errors"] = errors
        context["assignment_rules"] = ASSIGNMENT_RULES

        template = templates.get_template("modules/hr/templates/teams/pages/form.html")
        return HTMLResponse(template.render(context))

    update_data = HDTeamUpdateData(
        team_name=name,
        description=_form_str(form_data.get("description")),
        assignment_rule=_form_str(form_data.get("assignment_rule")),
        ignore_restrictions=_form_bool(form_data, "ignore_restrictions"),
    )

    service.update_hd_team(team_id, update_data)
    db.commit()

    return RedirectResponse(
        url=f"/hr/teams/{team_id}",
        status_code=303,
    )


@router.delete("/{team_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def team_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    team_id: int,
    _: CSRFProtect,
):
    """Delete a team."""
    service = OrganizationService(db)

    try:
        service.delete_hd_team(team_id)
        db.commit()
    except HDTeamNotFoundError:
        raise HTTPException(status_code=404, detail="Team not found")

    response.headers["HX-Redirect"] = "/hr/teams"
    return HTMLResponse("")


# Member management routes

@router.post("/{team_id}/members", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def add_team_member(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    team_id: int,
    _: CSRFProtect,
):
    """Add a member to the team."""
    form_data = await request.form()
    service = OrganizationService(db)

    try:
        team = service.get_hd_team(team_id)
    except HDTeamNotFoundError:
        raise HTTPException(status_code=404, detail="Team not found")

    user_email = _form_str(form_data.get("user"))
    if not user_email:
        raise HTTPException(status_code=400, detail="User email is required")

    member_data = TeamMemberData(
        user=user_email,
        user_name=_form_str(form_data.get("user_name")),
    )

    service.add_team_member(team_id, member_data)
    db.commit()

    # Return updated members list partial
    members = service.get_team_members(team_id)
    context = get_base_context(request, response, user, csrf_token)
    context["team"] = team
    context["members"] = members

    template = templates.get_template("modules/hr/templates/teams/partials/members_list.html")
    return HTMLResponse(template.render(context))


@router.delete("/{team_id}/members/{member_id}", response_class=HTMLResponse, dependencies=[RequireHRWrite])
async def remove_team_member(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    team_id: int,
    member_id: int,
    _: CSRFProtect,
):
    """Remove a member from the team."""
    service = OrganizationService(db)

    try:
        team = service.get_hd_team(team_id)
        service.remove_team_member(team_id, member_id)
        db.commit()
    except HDTeamNotFoundError:
        raise HTTPException(status_code=404, detail="Team not found")
    except Exception:
        raise HTTPException(status_code=404, detail="Member not found")

    # Return updated members list partial
    members = service.get_team_members(team_id)
    context = get_base_context(request, response, user, csrf_token)
    context["team"] = team
    context["members"] = members

    template = templates.get_template("modules/hr/templates/teams/partials/members_list.html")
    return HTMLResponse(template.render(context))
