"""
Data Cleanup Routes - Manage data quality scanning and cleanup operations.

Permission Requirements:
- admin:read - View issues and dashboard
- admin:write - Execute scans and cleanup operations

This module integrates with the CleanupService for all operations.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request, Response, Query, Depends
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.cleanup import (
    CleanupIssue,
    CleanupJob,
    CleanupScan,
    CleanupRule,
    IssueStatus,
    IssueSeverity,
    CleanupJobStatus,
    CleanupScanStatus,
    CleanupEntityType,
    CleanupIssueType,
)
from app.core.security import is_htmx_request, htmx_toast
from app.modules.settings.routes import get_settings_nav
from app.services.cleanup.service import CleanupService

# Permission dependencies
RequireCleanupRead = Depends(require_scope("admin:read"))
RequireCleanupWrite = Depends(require_scope("admin:write"))

router = APIRouter(prefix="/data-cleanup", tags=["settings-cleanup"])
templates = get_template_env()

# Status badge colors
SEVERITY_COLORS = {
    "critical": "bg-red-50 text-red-700 ring-red-600/20",
    "high": "bg-orange-50 text-orange-700 ring-orange-600/20",
    "medium": "bg-yellow-50 text-yellow-700 ring-yellow-600/20",
    "low": "bg-gray-50 text-gray-700 ring-gray-600/20",
}

ISSUE_STATUS_COLORS = {
    "open": "bg-blue-50 text-blue-700 ring-blue-600/20",
    "in_progress": "bg-amber-50 text-amber-700 ring-amber-600/20",
    "resolved": "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    "ignored": "bg-gray-50 text-gray-700 ring-gray-600/20",
}

JOB_STATUS_COLORS = {
    "pending": "bg-gray-50 text-gray-700 ring-gray-600/20",
    "previewing": "bg-purple-50 text-purple-700 ring-purple-600/20",
    "preview_ready": "bg-cyan-50 text-cyan-700 ring-cyan-600/20",
    "executing": "bg-amber-50 text-amber-700 ring-amber-600/20",
    "completed": "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    "failed": "bg-red-50 text-red-700 ring-red-600/20",
    "rolled_back": "bg-orange-50 text-orange-700 ring-orange-600/20",
}

SCAN_STATUS_COLORS = {
    "pending": "bg-gray-50 text-gray-700 ring-gray-600/20",
    "running": "bg-amber-50 text-amber-700 ring-amber-600/20",
    "completed": "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    "failed": "bg-red-50 text-red-700 ring-red-600/20",
}

# Entity type display names
ENTITY_DISPLAY_NAMES = {
    "customer": "Customers",
    "contact": "Contacts",
    "subscription": "Subscriptions",
    "supplier": "Suppliers",
    "employee": "Employees",
    "invoice": "Invoices",
    "payment": "Payments",
}

# Issue type display names
ISSUE_TYPE_DISPLAY = {
    "duplicate": "Duplicates",
    "invalid_format": "Invalid Format",
    "missing_required": "Missing Fields",
    "invalid_value": "Invalid Values",
    "orphaned": "Orphaned Records",
    "inconsistent": "Inconsistent Data",
    "stale": "Stale Data",
}


def get_entity_display(entity_type: str) -> str:
    """Get display name for entity type."""
    return ENTITY_DISPLAY_NAMES.get(entity_type, entity_type.replace("_", " ").title())


def get_issue_type_display(issue_type: str) -> str:
    """Get display name for issue type."""
    return ISSUE_TYPE_DISPLAY.get(issue_type, issue_type.replace("_", " ").title())


# =============================================================================
# DASHBOARD
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequireCleanupRead])
async def cleanup_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Data cleanup dashboard - overview of data quality."""
    service = CleanupService(db, user.id)
    stats = service.get_dashboard_stats()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Data Cleanup"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleanup"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleanup")

    # Dashboard data
    context["issue_counts"] = stats["issue_counts"]
    context["total_issues"] = stats["total_issues"]
    context["quality_score"] = stats["quality_score"]
    context["recent_issues"] = stats["recent_issues"]
    context["recent_jobs"] = stats["recent_jobs"]
    context["last_scan"] = stats["last_scan"]

    # Display helpers
    context["severity_colors"] = SEVERITY_COLORS
    context["issue_status_colors"] = ISSUE_STATUS_COLORS
    context["job_status_colors"] = JOB_STATUS_COLORS
    context["get_entity_display"] = get_entity_display
    context["get_issue_type_display"] = get_issue_type_display

    # Entity types for scan modal
    context["entity_types"] = [
        {"value": et.value, "label": get_entity_display(et.value)}
        for et in CleanupEntityType
    ]

    template = templates.get_template("modules/settings/templates/pages/cleanup/dashboard.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# ISSUES
# =============================================================================

@router.get("/issues", response_class=HTMLResponse, dependencies=[RequireCleanupRead])
async def issues_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    issue_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
):
    """List all cleanup issues."""
    per_page = 20
    service = CleanupService(db, user.id)

    issues, total = service.list_issues(
        status=status,
        severity=severity,
        entity_type=entity_type,
        issue_type=issue_type,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Data Quality Issues"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleanup", "href": "/settings/data-cleanup"},
        {"label": "Issues"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleanup")

    context["issues"] = issues
    context["pagination"] = build_pagination_context(page, per_page, total)

    # Filters
    context["current_status"] = status
    context["current_severity"] = severity
    context["current_entity_type"] = entity_type
    context["current_issue_type"] = issue_type

    # Filter options
    context["status_options"] = [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in IssueStatus
    ]
    context["severity_options"] = [
        {"value": s.value, "label": s.value.title()}
        for s in IssueSeverity
    ]
    context["entity_type_options"] = [
        {"value": et.value, "label": get_entity_display(et.value)}
        for et in CleanupEntityType
    ]
    context["issue_type_options"] = [
        {"value": it.value, "label": get_issue_type_display(it.value)}
        for it in CleanupIssueType
    ]

    # Display helpers
    context["severity_colors"] = SEVERITY_COLORS
    context["issue_status_colors"] = ISSUE_STATUS_COLORS
    context["get_entity_display"] = get_entity_display
    context["get_issue_type_display"] = get_issue_type_display

    template = templates.get_template("modules/settings/templates/pages/cleanup/issues_list.html")
    return HTMLResponse(template.render(context))


@router.get("/issues/{issue_id}", response_class=HTMLResponse, dependencies=[RequireCleanupRead])
async def issue_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    issue_id: int,
):
    """View issue detail with affected records."""
    service = CleanupService(db, user.id)
    issue = service.get_issue(issue_id)

    if not issue:
        # Return 404
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Issue Not Found"
        template = templates.get_template("errors/404.html")
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Issue #{issue.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleanup", "href": "/settings/data-cleanup"},
        {"label": "Issues", "href": "/settings/data-cleanup/issues"},
        {"label": f"Issue #{issue.id}"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleanup")

    context["issue"] = issue
    context["severity_colors"] = SEVERITY_COLORS
    context["issue_status_colors"] = ISSUE_STATUS_COLORS
    context["get_entity_display"] = get_entity_display
    context["get_issue_type_display"] = get_issue_type_display

    template = templates.get_template("modules/settings/templates/pages/cleanup/issue_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# JOBS
# =============================================================================

@router.get("/jobs", response_class=HTMLResponse, dependencies=[RequireCleanupRead])
async def jobs_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
):
    """List all cleanup jobs."""
    per_page = 20
    service = CleanupService(db, user.id)

    jobs, total = service.list_jobs(
        status=status,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Cleanup Jobs"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleanup", "href": "/settings/data-cleanup"},
        {"label": "Jobs"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleanup")

    context["jobs"] = jobs
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["current_status"] = status

    context["status_options"] = [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in CleanupJobStatus
    ]
    context["job_status_colors"] = JOB_STATUS_COLORS
    context["get_entity_display"] = get_entity_display

    template = templates.get_template("modules/settings/templates/pages/cleanup/jobs_list.html")
    return HTMLResponse(template.render(context))


@router.get("/jobs/{job_id}", response_class=HTMLResponse, dependencies=[RequireCleanupRead])
async def job_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
):
    """View job detail with results."""
    service = CleanupService(db, user.id)
    job = service.get_job(job_id)

    if not job:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Job Not Found"
        template = templates.get_template("errors/404.html")
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Job: {job.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleanup", "href": "/settings/data-cleanup"},
        {"label": "Jobs", "href": "/settings/data-cleanup/jobs"},
        {"label": job.name},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleanup")

    context["job"] = job
    context["job_status_colors"] = JOB_STATUS_COLORS
    context["get_entity_display"] = get_entity_display

    template = templates.get_template("modules/settings/templates/pages/cleanup/job_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# RULES
# =============================================================================

@router.get("/rules", response_class=HTMLResponse, dependencies=[RequireCleanupRead])
async def rules_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    page: int = Query(1, ge=1),
):
    """List all cleanup rules."""
    per_page = 20
    service = CleanupService(db, user.id)

    rules, total = service.list_rules(
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Cleanup Rules"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleanup", "href": "/settings/data-cleanup"},
        {"label": "Rules"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleanup")

    context["rules"] = rules
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["get_entity_display"] = get_entity_display
    context["get_issue_type_display"] = get_issue_type_display

    template = templates.get_template("modules/settings/templates/pages/cleanup/rules_list.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# SCANS
# =============================================================================

@router.get("/scans", response_class=HTMLResponse, dependencies=[RequireCleanupRead])
async def scans_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    page: int = Query(1, ge=1),
):
    """List all cleanup scans."""
    per_page = 20
    service = CleanupService(db, user.id)

    scans, total = service.list_scans(
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Scan History"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleanup", "href": "/settings/data-cleanup"},
        {"label": "Scans"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleanup")

    context["scans"] = scans
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["scan_status_colors"] = SCAN_STATUS_COLORS

    template = templates.get_template("modules/settings/templates/pages/cleanup/scans_list.html")
    return HTMLResponse(template.render(context))
