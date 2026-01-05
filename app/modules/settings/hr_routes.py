"""
HR Settings Routes - Human Resources module configuration.

Handles leave, attendance, payroll, benefits, and compliance settings.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, Depends, UploadFile
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import get_base_context, get_navigation_context, build_breadcrumbs
from app.templates.environment import get_template_env
from app.core.security import set_flash
from app.services.settings_hr_service import SettingsHRService

# Permission dependencies
RequireHRSettingsRead = Depends(require_scope("hr:settings:read"))
RequireHRSettingsWrite = Depends(require_scope("hr:settings:write"))

router = APIRouter(prefix="/hr", tags=["settings-hr"])
templates = get_template_env()


def _form_int(form: Any, key: str, default: int) -> int:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    try:
        return int(value) if value not in ("", None) else default
    except (TypeError, ValueError):
        return default


def _form_float(form: Any, key: str, default: float) -> float:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    try:
        return float(value) if value not in ("", None) else default
    except (TypeError, ValueError):
        return default


def _form_bool(form: Any, key: str) -> bool:
    value = form.get(key)
    if isinstance(value, UploadFile):
        return False
    return value in ("true", "on", "1", True)


def get_settings_nav(user, current_section: str = "hr") -> list[dict]:
    """Get settings navigation."""
    from app.modules.settings.routes import SETTINGS_CATEGORIES
    nav_items = []
    for cat in SETTINGS_CATEGORIES:
        if cat["scope"] is None or user.has_scope(cat["scope"]):
            nav_items.append({
                **cat,
                "is_current": current_section == cat["id"],
            })
    return nav_items


HR_TABS = [
    {"id": "general", "label": "General", "href": "/settings/hr"},
    {"id": "leave", "label": "Leave Policies", "href": "/settings/hr/leave-policies"},
    {"id": "holidays", "label": "Holidays", "href": "/settings/hr/holidays"},
    {"id": "salary", "label": "Salary Bands", "href": "/settings/hr/salary-bands"},
    {"id": "deductions", "label": "Deductions", "href": "/settings/hr/deductions"},
]


@router.get("", response_class=HTMLResponse, dependencies=[RequireHRSettingsRead])
async def hr_settings_index(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """HR settings - general configuration with collapsible sections."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "hr")
    context["hr_tabs"] = HR_TABS
    context["current_tab"] = "general"

    service = SettingsHRService(db)
    settings = service.get_settings()

    context["page_title"] = "HR Settings"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "HR & Payroll", "href": "/settings/hr"},
        {"label": "General"},
    ])

    context["settings"] = settings
    context["can_edit"] = user.has_scope("hr:settings:write")

    template = templates.get_template("modules/settings/templates/pages/hr/general.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireHRSettingsWrite])
async def save_hr_settings(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _csrf: CSRFProtect,
):
    """Save HR settings."""
    form = await request.form()

    service = SettingsHRService(db)
    values: dict[str, Any] = {
        # Leave policy fields
        "max_carryforward_days": _form_int(form, "max_carryforward_days", 5),
        "min_leave_notice_days": _form_int(form, "min_leave_notice_days", 1),
        "allow_negative_leave_balance": _form_bool(form, "allow_negative_leave_balance"),
        "sick_leave_auto_approve_days": _form_int(form, "sick_leave_auto_approve_days", 0),
        "medical_certificate_required_after_days": _form_int(form, "medical_certificate_required_after_days", 2),
        # Attendance fields
        "late_entry_grace_minutes": _form_int(form, "late_entry_grace_minutes", 15),
        "half_day_hours_threshold": _form_float(form, "half_day_hours_threshold", 4.0),
        "geolocation_required": _form_bool(form, "geolocation_required"),
        "geolocation_radius_meters": _form_int(form, "geolocation_radius_meters", 100),
        # Payroll fields
        "salary_payment_day": _form_int(form, "salary_payment_day", 25),
        "payroll_cutoff_day": _form_int(form, "payroll_cutoff_day", 20),
        "allow_salary_advance": _form_bool(form, "allow_salary_advance"),
        "max_advance_percent": _form_int(form, "max_advance_percent", 50),
        # Benefits fields
        "gratuity_enabled": _form_bool(form, "gratuity_enabled"),
        "pension_enabled": _form_bool(form, "pension_enabled"),
        "pension_employer_percent": _form_float(form, "pension_employer_percent", 10.0),
        "pension_employee_percent": _form_float(form, "pension_employee_percent", 8.0),
        # Compliance fields
        "standard_work_hours_per_day": _form_float(form, "standard_work_hours_per_day", 8.0),
        "max_work_hours_per_day": _form_float(form, "max_work_hours_per_day", 12.0),
        "default_probation_months": _form_int(form, "default_probation_months", 3),
        "default_notice_period_days": _form_int(form, "default_notice_period_days", 30),
    }
    service.save_settings(values)

    set_flash(response, "HR settings saved successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/settings/hr", status_code=303)


@router.get("/leave-policies", response_class=HTMLResponse, dependencies=[RequireHRSettingsRead])
async def leave_policies_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Leave encashment policies."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "hr")
    context["hr_tabs"] = HR_TABS
    context["current_tab"] = "leave"

    service = SettingsHRService(db)
    policies = service.list_leave_policies()

    context["page_title"] = "Leave Policies"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "HR & Payroll", "href": "/settings/hr"},
        {"label": "Leave Policies"},
    ])

    context["policies"] = policies
    context["can_edit"] = user.has_scope("hr:settings:write")

    template = templates.get_template("modules/settings/templates/pages/hr/leave_policies.html")
    return HTMLResponse(template.render(context))


@router.get("/holidays", response_class=HTMLResponse, dependencies=[RequireHRSettingsRead])
async def holidays_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Holiday calendars."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "hr")
    context["hr_tabs"] = HR_TABS
    context["current_tab"] = "holidays"

    service = SettingsHRService(db)
    calendars = service.list_holiday_calendars()

    context["page_title"] = "Holiday Calendars"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "HR & Payroll", "href": "/settings/hr"},
        {"label": "Holidays"},
    ])

    context["calendars"] = calendars
    context["can_edit"] = user.has_scope("hr:settings:write")

    template = templates.get_template("modules/settings/templates/pages/hr/holidays.html")
    return HTMLResponse(template.render(context))


@router.get("/salary-bands", response_class=HTMLResponse, dependencies=[RequireHRSettingsRead])
async def salary_bands_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Salary bands."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "hr")
    context["hr_tabs"] = HR_TABS
    context["current_tab"] = "salary"

    service = SettingsHRService(db)
    bands = service.list_salary_bands()

    context["page_title"] = "Salary Bands"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "HR & Payroll", "href": "/settings/hr"},
        {"label": "Salary Bands"},
    ])

    context["bands"] = bands
    context["can_edit"] = user.has_scope("hr:settings:write")

    template = templates.get_template("modules/settings/templates/pages/hr/salary_bands.html")
    return HTMLResponse(template.render(context))


@router.get("/deductions", response_class=HTMLResponse, dependencies=[RequireHRSettingsRead])
async def deductions_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Employment type deduction configurations."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["settings_nav"] = get_settings_nav(user, "hr")
    context["hr_tabs"] = HR_TABS
    context["current_tab"] = "deductions"

    service = SettingsHRService(db)
    configs = service.list_deduction_configs()

    context["page_title"] = "Deduction Configurations"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "HR & Payroll", "href": "/settings/hr"},
        {"label": "Deductions"},
    ])

    context["configs"] = configs
    context["can_edit"] = user.has_scope("hr:settings:write")

    template = templates.get_template("modules/settings/templates/pages/hr/deductions.html")
    return HTMLResponse(template.render(context))
