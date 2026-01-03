"""
HR Org Chart Routes - Organization Chart Visualization with SSR + HTMX.

Permission Requirements:
- hr:read - View org chart

Uses EmployeeService for all business logic.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
)
from app.templates.environment import get_template_env
from app.services.hr.employees import EmployeeService
from app.services.hr.errors import EmployeeNotFoundError

RequireHRRead = Depends(require_scope("hr:read"))

router = APIRouter(prefix="/org-chart", tags=["hr-org-chart"])
templates = get_template_env()


def _serialize_org_node(node: Any) -> Dict[str, Any]:
    """Serialize org chart node for JSON."""
    return {
        "id": node.id,
        "name": node.employee_name or "Unknown",
        "designation": node.designation or "",
        "department": node.department or "",
        "image": node.image if hasattr(node, "image") else None,
        "children": [_serialize_org_node(child) for child in (node.children or [])],
    }


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def org_chart_view(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    root_id: Optional[int] = Query(None, description="Root employee ID"),
    depth: int = Query(4, ge=1, le=10, description="Tree depth"),
):
    """Org chart visualization page."""
    service = EmployeeService(db, user)

    # Get org chart data
    if root_id:
        try:
            nodes = service.get_org_chart(root_employee_id=root_id, depth=depth)
        except EmployeeNotFoundError:
            raise HTTPException(status_code=404, detail="Employee not found")
    else:
        nodes = service.get_org_chart(root_employee_id=None, depth=depth)

    # Serialize for template/JS
    org_data = [_serialize_org_node(node) for node in nodes]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Organization Chart"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR", "href": "/hr/employees"},
        {"label": "Organization Chart"},
    ])
    context["org_data"] = org_data
    context["depth"] = depth
    context["root_id"] = root_id

    template = templates.get_template("modules/hr/templates/org_chart/pages/view.html")
    return HTMLResponse(template.render(context))
