"""
HR Dashboard Routes - HR Overview with SSR + HTMX.

Permission Requirements:
- hr:read - View HR dashboard
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Request, Response, Depends, Query
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
)
from app.templates.environment import get_template_env
from app.services.hr.analytics import HRAnalyticsService

RequireHRRead = Depends(require_scope("hr:read"))

router = APIRouter(tags=["hr-dashboard"])
templates = get_template_env()


@router.get("/", response_class=HTMLResponse, dependencies=[RequireHRRead])
async def hr_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    as_at: Optional[str] = Query(None, description="View as at date (YYYY-MM-DD)"),
):
    """HR Dashboard with overview stats and quick actions.

    Args:
        as_at: Optional date string to view historical data (YYYY-MM-DD format)
    """
    # Parse as_at date filter
    view_date: Optional[date] = None
    if as_at:
        try:
            view_date = datetime.strptime(as_at, "%Y-%m-%d").date()
        except ValueError:
            pass  # Invalid date format, use today

    # Use service for all dashboard data
    analytics_service = HRAnalyticsService(db)
    try:
        dashboard_data = analytics_service.get_dashboard_data(as_at=view_date)
    except Exception:
        dashboard_data = None

    # Birthday tracking is omitted (Employee has no date_of_birth field)
    employees_with_birthdays: list = []

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "HR Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "HR"},
    ])

    # Map service dataclass to template format
    if dashboard_data:
        context["stats"] = {
            "total_employees": dashboard_data.stats.total_employees,
            "present_today": dashboard_data.stats.present_today,
            "on_leave_today": dashboard_data.stats.on_leave_today,
            "pending_leave": dashboard_data.stats.pending_leave,
        }
        context["recent_leave_requests"] = dashboard_data.recent_leave_requests
        context["department_stats"] = [
            {"id": d.id, "name": d.name, "count": d.count}
            for d in dashboard_data.department_stats
        ]
        context["anniversaries"] = [
            {"id": a.id, "name": a.name, "date": a.date, "years": a.years}
            for a in dashboard_data.anniversaries
        ]
        context["next_payroll"] = (
            {"id": dashboard_data.next_payroll.id, "name": dashboard_data.next_payroll.name, "date": dashboard_data.next_payroll.date}
            if dashboard_data.next_payroll
            else None
        )
    else:
        context["stats"] = {
            "total_employees": 0,
            "present_today": 0,
            "on_leave_today": 0,
            "pending_leave": 0,
        }
        context["recent_leave_requests"] = []
        context["department_stats"] = []
        context["anniversaries"] = []
        context["next_payroll"] = None
    context["birthdays"] = employees_with_birthdays
    context["today"] = date.today()
    context["as_at"] = view_date  # For date picker
    context["view_date"] = view_date or date.today()  # Actual date being viewed

    template = templates.get_template("modules/hr/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))
