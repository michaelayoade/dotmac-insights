"""
Settings Routes - Main router for centralized settings UI.

Aggregates all settings sub-routes and provides the settings dashboard.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, require_scope
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.schemas.settings_schemas import get_all_groups

# Permission dependencies
RequireSettingsRead = Depends(require_scope("settings:read"))
RequireAdminRead = Depends(require_scope("admin:read"))

router: APIRouter = APIRouter(prefix="/settings", tags=["settings"])
templates = get_template_env()


# Settings categories for dashboard
SETTINGS_CATEGORIES = [
    {
        "id": "general",
        "name": "General",
        "description": "Email, payments, SMS, notifications, and branding",
        "icon": "cog",
        "href": "/settings/general",
        "scope": "settings:read",
        "color": "blue",
    },
    {
        "id": "admin",
        "name": "Admin",
        "description": "Users, roles, permissions, and service tokens",
        "icon": "shield",
        "href": "/settings/admin",
        "scope": "admin:read",
        "color": "purple",
    },
    {
        "id": "books",
        "name": "Accounting",
        "description": "Currency, fiscal year, and document numbering",
        "icon": "book",
        "href": "/settings/books",
        "scope": "books:settings:read",
        "color": "emerald",
    },
    {
        "id": "hr",
        "name": "HR & Payroll",
        "description": "Leave, attendance, payroll, and benefits policies",
        "icon": "users",
        "href": "/settings/hr",
        "scope": "hr:settings:read",
        "color": "amber",
    },
    {
        "id": "support",
        "name": "Support",
        "description": "SLA, escalations, queues, and customer portal",
        "icon": "life-buoy",
        "href": "/settings/support",
        "scope": "support:settings:read",
        "color": "cyan",
    },
    {
        "id": "assets",
        "name": "Assets",
        "description": "Depreciation methods and alert thresholds",
        "icon": "box",
        "href": "/settings/assets",
        "scope": "assets:settings:read",
        "color": "rose",
    },
    {
        "id": "sync",
        "name": "Data Sync",
        "description": "Splynx, ERPNext, and Chatwoot synchronization",
        "icon": "refresh",
        "href": "/settings/sync",
        "scope": "settings:sync",
        "color": "indigo",
    },
    {
        "id": "migration",
        "name": "Data Migration",
        "description": "Import data from CSV, JSON, and Excel files",
        "icon": "upload",
        "href": "/settings/migration",
        "scope": "admin:write",
        "color": "violet",
    },
    {
        "id": "data-cleanup",
        "name": "Data Cleanup",
        "description": "Scan, clean, and normalize data quality issues",
        "icon": "check-circle",
        "href": "/settings/data-cleanup",
        "scope": "admin:read",
        "color": "teal",
    },
]


def get_settings_nav(user, current_section: str = "") -> list[dict]:
    """Get settings navigation filtered by user permissions."""
    nav_items = []
    for cat in SETTINGS_CATEGORIES:
        if cat["scope"] is None or user.has_scope(cat["scope"]):
            nav_items.append({
                **cat,
                "is_current": current_section == cat["id"],
            })
    return nav_items


@router.get("", response_class=HTMLResponse, dependencies=[RequireSettingsRead])
async def settings_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """Settings dashboard - overview of all settings sections."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Settings"

    # Filter categories by user permissions
    categories = [
        cat for cat in SETTINGS_CATEGORIES
        if cat["scope"] is None or user.has_scope(cat["scope"])
    ]
    context["categories"] = categories
    context["settings_nav"] = get_settings_nav(user)

    template = templates.get_template("modules/settings/templates/pages/index.html")
    return HTMLResponse(template.render(context))


# Import and include sub-routers
from app.modules.settings.general_routes import router as general_router
from app.modules.settings.admin_routes import router as admin_router
from app.modules.settings.books_routes import router as books_router
from app.modules.settings.hr_routes import router as hr_router
from app.modules.settings.support_routes import router as support_router
from app.modules.settings.assets_routes import router as assets_router
from app.modules.settings.sync_routes import router as sync_router
from app.modules.settings.cleanup_routes import router as cleanup_router
from app.modules.settings.migration_routes import router as migration_router

router.include_router(general_router)
router.include_router(admin_router)
router.include_router(books_router)
router.include_router(hr_router)
router.include_router(support_router)
router.include_router(assets_router)
router.include_router(sync_router)
router.include_router(cleanup_router)
router.include_router(migration_router)


# Redirect for workflow tasks - consolidated under settings
from fastapi.responses import RedirectResponse


@router.get("/tasks")
async def settings_tasks_redirect():
    """Redirect to workflow tasks."""
    return RedirectResponse(url="/workflow-tasks", status_code=302)


@router.get("/tasks/{path:path}")
async def settings_tasks_path_redirect(path: str):
    """Redirect workflow task sub-paths."""
    return RedirectResponse(url=f"/workflow-tasks/{path}", status_code=302)
