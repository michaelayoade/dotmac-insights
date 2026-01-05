"""
Data Cleaner Routes - Bulk editing and data normalization UI.

Permission Requirements:
- admin:read - View previews and operation history
- admin:write - Execute cleaning operations

This module integrates with the DataCleanerService for all operations.
"""
from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, Request, Response, Query, Depends, Form
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.services.settings_cleaner_service import SettingsCleanerService
from app.core.security import is_htmx_request, htmx_toast
from app.modules.settings.routes import get_settings_nav
from app.services.data_explorer import DataCleanerService, DataExplorerService

# Permission dependencies
RequireCleanerRead = Depends(require_scope("admin:read"))
RequireCleanerWrite = Depends(require_scope("admin:write"))

router = APIRouter(prefix="/data-cleaner", tags=["settings-cleaner"])
templates = get_template_env()

# Operation status colors
OPERATION_COLORS = {
    "pending": "bg-gray-50 text-gray-700 ring-gray-600/20",
    "executing": "bg-amber-50 text-amber-700 ring-amber-600/20",
    "completed": "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    "failed": "bg-red-50 text-red-700 ring-red-600/20",
    "rolled_back": "bg-purple-50 text-purple-700 ring-purple-600/20",
}

# Operation type display names
OPERATION_TYPE_DISPLAY = {
    "bulk_update": "Bulk Update",
    "normalize": "Normalization",
    "merge": "Duplicate Merge",
    "link": "Orphan Linking",
}

# Cleanable tables for dropdowns
CLEANABLE_TABLES = [
    {"value": "parties", "label": "Parties"},
    {"value": "customer_accounts", "label": "Customer Accounts"},
    {"value": "leads", "label": "Leads"},
    {"value": "invoices", "label": "Invoices"},
    {"value": "payments", "label": "Payments"},
    {"value": "tickets", "label": "Tickets"},
    {"value": "subscriptions", "label": "Subscriptions"},
]

# Match fields for duplicate detection
MATCH_FIELDS = [
    {"value": "primary_email", "label": "Email"},
    {"value": "primary_phone", "label": "Phone"},
    {"value": "name", "label": "Name"},
]

# FK fields for orphan detection
ORPHAN_FK_OPTIONS = {
    "invoices": [
        {"value": "customer_account_id", "label": "Customer Account"},
        {"value": "party_id", "label": "Party"},
    ],
    "payments": [
        {"value": "customer_account_id", "label": "Customer Account"},
        {"value": "party_id", "label": "Party"},
    ],
    "tickets": [
        {"value": "customer_account_id", "label": "Customer Account"},
        {"value": "assigned_employee_id", "label": "Assigned Employee"},
    ],
    "subscriptions": [
        {"value": "customer_account_id", "label": "Customer Account"},
        {"value": "party_id", "label": "Party"},
    ],
}


def get_operation_type_display(op_type: str) -> str:
    """Get display name for operation type."""
    return OPERATION_TYPE_DISPLAY.get(op_type, op_type.replace("_", " ").title())


# =============================================================================
# DASHBOARD
# =============================================================================


@router.get("", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def cleaner_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Data cleaner dashboard - overview and quick actions."""
    cleaner = DataCleanerService(db, user)
    explorer = DataExplorerService(db, user)

    # Get data quality report
    quality = explorer.check_data_quality()

    # Get recent operations
    recent_ops = cleaner.list_operations(limit=5)

    # Get quick stats
    phone_preview = cleaner.preview_normalize_phones()
    email_preview = cleaner.preview_normalize_emails()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Data Cleaner"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleaner"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleaner")

    # Dashboard data
    context["quality"] = quality
    context["recent_operations"] = recent_ops
    context["phone_stats"] = {
        "to_normalize": phone_preview.records_to_normalize,
        "invalid": phone_preview.invalid_values,
    }
    context["email_stats"] = {
        "to_normalize": email_preview.records_to_normalize,
        "invalid": email_preview.invalid_values,
    }

    # Display helpers
    context["operation_colors"] = OPERATION_COLORS
    context["get_operation_type_display"] = get_operation_type_display

    if is_htmx_request(request):
        template = templates.get_template(
            "modules/settings/templates/pages/cleaner/partials/dashboard_content.html"
        )
        return HTMLResponse(template.render(context))

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/dashboard.html"
    )
    return HTMLResponse(template.render(context))


# =============================================================================
# NORMALIZATION
# =============================================================================


@router.get("/normalize", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def normalize_page(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Normalization page - phone and email standardization."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Normalize Data"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleaner", "href": "/settings/data-cleaner"},
        {"label": "Normalize"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleaner")

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/normalize.html"
    )
    return HTMLResponse(template.render(context))


@router.post("/normalize/preview", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def normalize_preview(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    field: str = Form(...),
):
    """HTMX: Preview normalization changes."""
    cleaner = DataCleanerService(db, user)

    if field == "phones":
        preview = cleaner.preview_normalize_phones()
    else:
        preview = cleaner.preview_normalize_emails()

    context = get_base_context(request, response, user, csrf_token)
    context["preview"] = preview
    context["field"] = field

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/partials/normalize_preview.html"
    )
    return HTMLResponse(template.render(context))


@router.post("/normalize/execute", response_class=HTMLResponse, dependencies=[RequireCleanerWrite])
async def normalize_execute(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    field: str = Form(...),
):
    """Execute normalization."""
    service = SettingsCleanerService(db, principal=user)
    result = service.execute_normalize(field)

    # Return success with redirect
    response.headers["HX-Redirect"] = f"/settings/data-cleaner/operations/{result.operation_id}"
    return HTMLResponse(
        htmx_toast(f"Normalized {result.records_normalized} records", "success"),
        headers={"HX-Redirect": f"/settings/data-cleaner/operations"}
    )


# =============================================================================
# DUPLICATES
# =============================================================================


@router.get("/duplicates", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def duplicates_page(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Duplicate detection page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Find Duplicates"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleaner", "href": "/settings/data-cleaner"},
        {"label": "Duplicates"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleaner")
    context["tables"] = CLEANABLE_TABLES
    context["match_fields"] = MATCH_FIELDS

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/duplicates.html"
    )
    return HTMLResponse(template.render(context))


@router.post("/duplicates/scan", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def duplicates_scan(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    table: str = Form(...),
    match_fields: List[str] = Form(...),
):
    """HTMX: Scan for duplicates."""
    cleaner = DataCleanerService(db, user)
    report = cleaner.find_duplicates(table, match_fields)

    context = get_base_context(request, response, user, csrf_token)
    context["report"] = report
    context["table"] = table

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/partials/duplicates_table.html"
    )
    return HTMLResponse(template.render(context))


@router.get("/duplicates/merge", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def duplicates_merge_page(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    table: str = Query(...),
    ids: str = Query(...),  # Comma-separated IDs
):
    """Merge wizard for duplicate group."""
    cleaner = DataCleanerService(db, user)

    record_ids = [int(x) for x in ids.split(",")]
    primary_id = record_ids[0]
    duplicate_ids = record_ids[1:]

    preview = cleaner.preview_merge_duplicates(table, primary_id, duplicate_ids)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Merge Duplicates"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleaner", "href": "/settings/data-cleaner"},
        {"label": "Duplicates", "href": "/settings/data-cleaner/duplicates"},
        {"label": "Merge"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleaner")
    context["preview"] = preview
    context["table"] = table
    context["primary_id"] = primary_id
    context["duplicate_ids"] = duplicate_ids

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/duplicates_merge.html"
    )
    return HTMLResponse(template.render(context))


@router.post("/duplicates/merge", response_class=HTMLResponse, dependencies=[RequireCleanerWrite])
async def duplicates_merge_execute(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    table: str = Form(...),
    primary_id: int = Form(...),
    duplicate_ids: str = Form(...),  # Comma-separated
):
    """Execute duplicate merge."""
    service = SettingsCleanerService(db, principal=user)
    dup_ids = [int(x) for x in duplicate_ids.split(",")]
    result = service.execute_merge_duplicates(table, primary_id, dup_ids)

    return HTMLResponse(
        htmx_toast(f"Merged {len(result.merged_ids)} records", "success"),
        headers={"HX-Redirect": "/settings/data-cleaner/operations"}
    )


# =============================================================================
# ORPHANS
# =============================================================================


@router.get("/orphans", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def orphans_page(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Orphan linking page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Link Orphans"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleaner", "href": "/settings/data-cleaner"},
        {"label": "Orphans"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleaner")
    context["tables"] = CLEANABLE_TABLES
    context["fk_options"] = ORPHAN_FK_OPTIONS

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/orphans.html"
    )
    return HTMLResponse(template.render(context))


@router.post("/orphans/scan", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def orphans_scan(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    table: str = Form(...),
    fk_field: str = Form(...),
):
    """HTMX: Scan for orphan records."""
    cleaner = DataCleanerService(db, user)
    report = cleaner.find_orphans(table, fk_field)

    context = get_base_context(request, response, user, csrf_token)
    context["report"] = report
    context["table"] = table
    context["fk_field"] = fk_field

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/partials/orphans_table.html"
    )
    return HTMLResponse(template.render(context))


# =============================================================================
# BULK UPDATE
# =============================================================================


@router.get("/bulk-update", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def bulk_update_page(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Bulk update page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Bulk Update"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleaner", "href": "/settings/data-cleaner"},
        {"label": "Bulk Update"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleaner")
    context["tables"] = CLEANABLE_TABLES

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/bulk_update.html"
    )
    return HTMLResponse(template.render(context))


@router.post("/bulk-update/preview", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def bulk_update_preview(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """HTMX: Preview bulk update changes."""
    form = await request.form()
    table = form.get("table")

    # Parse filters and updates from form
    filters = {}
    updates = {}

    for key, value in form.items():
        if key.startswith("filter_") and value:
            field = key.replace("filter_", "")
            filters[field] = value
        elif key.startswith("update_") and value:
            field = key.replace("update_", "")
            updates[field] = value

    cleaner = DataCleanerService(db, user)
    preview = cleaner.preview_bulk_update(table, filters, updates)

    context = get_base_context(request, response, user, csrf_token)
    context["preview"] = preview
    context["table"] = table
    context["filters"] = filters
    context["updates"] = updates

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/partials/bulk_update_preview.html"
    )
    return HTMLResponse(template.render(context))


@router.post("/bulk-update/execute", response_class=HTMLResponse, dependencies=[RequireCleanerWrite])
async def bulk_update_execute(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Execute bulk update."""
    form = await request.form()
    table = form.get("table")

    filters = {}
    updates = {}

    for key, value in form.items():
        if key.startswith("filter_") and value:
            field = key.replace("filter_", "")
            filters[field] = value
        elif key.startswith("update_") and value:
            field = key.replace("update_", "")
            updates[field] = value

    service = SettingsCleanerService(db, principal=user)
    result = service.execute_bulk_update(table, filters, updates)

    return HTMLResponse(
        htmx_toast(f"Updated {result.records_updated} records", "success"),
        headers={"HX-Redirect": "/settings/data-cleaner/operations"}
    )


# =============================================================================
# OPERATIONS HISTORY
# =============================================================================


@router.get("/operations", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def operations_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
    op_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """Operation history page."""
    # Get operations with pagination
    offset = (page - 1) * per_page
    service = SettingsCleanerService(db, principal=user)
    operations = service.list_operations(limit=per_page, offset=offset)

    # Get total count for pagination
    total = service.count_operations()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Operation History"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleaner", "href": "/settings/data-cleaner"},
        {"label": "Operations"},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleaner")

    context["operations"] = operations
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["operation_colors"] = OPERATION_COLORS
    context["get_operation_type_display"] = get_operation_type_display

    # Filter options
    context["type_options"] = [
        {"value": "bulk_update", "label": "Bulk Update"},
        {"value": "normalize", "label": "Normalization"},
        {"value": "merge", "label": "Merge"},
        {"value": "link", "label": "Link"},
    ]
    context["status_options"] = [
        {"value": "pending", "label": "Pending"},
        {"value": "executing", "label": "Executing"},
        {"value": "completed", "label": "Completed"},
        {"value": "failed", "label": "Failed"},
        {"value": "rolled_back", "label": "Rolled Back"},
    ]
    context["current_type"] = op_type
    context["current_status"] = status

    if is_htmx_request(request):
        template = templates.get_template(
            "modules/settings/templates/pages/cleaner/partials/operations_table.html"
        )
        return HTMLResponse(template.render(context))

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/operations.html"
    )
    return HTMLResponse(template.render(context))


@router.get("/operations/{operation_id}", response_class=HTMLResponse, dependencies=[RequireCleanerRead])
async def operation_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    operation_id: str,
):
    """Operation detail page."""
    service = SettingsCleanerService(db, principal=user)
    operation = service.get_operation(operation_id)

    if not operation:
        return HTMLResponse("Operation not found", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Operation {operation_id[:8]}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Cleaner", "href": "/settings/data-cleaner"},
        {"label": "Operations", "href": "/settings/data-cleaner/operations"},
        {"label": operation_id[:8]},
    ])
    context["settings_nav"] = get_settings_nav(user, "data-cleaner")

    context["operation"] = operation
    context["operation_colors"] = OPERATION_COLORS
    context["get_operation_type_display"] = get_operation_type_display

    template = templates.get_template(
        "modules/settings/templates/pages/cleaner/operation_detail.html"
    )
    return HTMLResponse(template.render(context))


@router.post("/operations/{operation_id}/rollback", response_class=HTMLResponse, dependencies=[RequireCleanerWrite])
async def operation_rollback(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    operation_id: str,
):
    """Rollback an operation."""
    service = SettingsCleanerService(db, principal=user)
    result = service.rollback_operation(operation_id)

    if result.success:
        return HTMLResponse(
            htmx_toast(f"Rolled back {result.records_restored} records", "success"),
            headers={"HX-Refresh": "true"}
        )
    else:
        return HTMLResponse(
            htmx_toast(f"Rollback failed: {len(result.errors)} errors", "error"),
            headers={"HX-Refresh": "true"}
        )
