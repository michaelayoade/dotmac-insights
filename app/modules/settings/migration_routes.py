"""
Migration Management Routes - Manage data migration jobs from CSV, JSON, and Excel files.

Permission Requirements:
- admin:write - Create and manage migration jobs

This module integrates with the MigrationService for all operations.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, desc

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.migration import (
    MigrationJob,
    MigrationRecord,
    MigrationStatus,
    EntityType,
    DedupStrategy,
    RecordAction,
)
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.modules.settings.routes import get_settings_nav
from app.utils.datetime_utils import utc_now

# Import migration service and registry
from app.services.migration.service import MigrationService
from app.services.migration.registry import (
    list_entities,
    get_entity_config,
    get_entity_fields,
    get_migration_order,
    get_dependencies,
)

# Permission dependencies
RequireMigrationRead = Depends(require_scope("admin:read"))
RequireMigrationWrite = Depends(require_scope("admin:write"))

router = APIRouter(prefix="/migration", tags=["settings-migration"])
templates = get_template_env()

# Upload directory
UPLOAD_DIR = "/tmp/migration_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Status badge colors
MIGRATION_STATUS_COLORS = {
    'pending': 'bg-gray-50 text-gray-700 ring-gray-600/20',
    'uploaded': 'bg-blue-50 text-blue-700 ring-blue-600/20',
    'mapped': 'bg-indigo-50 text-indigo-700 ring-indigo-600/20',
    'validating': 'bg-purple-50 text-purple-700 ring-purple-600/20',
    'validated': 'bg-cyan-50 text-cyan-700 ring-cyan-600/20',
    'running': 'bg-amber-50 text-amber-700 ring-amber-600/20',
    'completed': 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    'failed': 'bg-red-50 text-red-700 ring-red-600/20',
    'cancelled': 'bg-gray-50 text-gray-700 ring-gray-600/20',
    'rolled_back': 'bg-orange-50 text-orange-700 ring-orange-600/20',
}

# Entity type categories for display
ENTITY_CATEGORIES = {
    "Core": ["contacts", "customers", "employees", "departments", "designations"],
    "Accounting": ["accounts", "bank_accounts", "journal_entries", "invoices", "payments", "credit_notes"],
    "Purchasing": ["suppliers", "purchase_invoices", "supplier_payments"],
    "HR": ["leave_types", "holiday_lists", "leave_policies", "leave_allocations", "leave_applications",
           "shift_types", "attendances", "salary_components", "salary_structures", "payroll_entries"],
    "CRM": ["leads", "opportunities", "activities", "campaigns"],
    "Support": ["tickets", "unified_tickets", "agents", "canned_responses"],
    "Inventory": ["items", "warehouses", "stock_entries", "batches", "serial_numbers"],
    "Projects": ["projects", "tasks"],
    "Assets": ["asset_categories", "assets"],
    "Expenses": ["expenses", "expense_claims", "cash_advances"],
}


def get_entity_display_name(entity_type: str) -> str:
    """Get display name for entity type."""
    return entity_type.replace("_", " ").title()


def get_entity_category(entity_type: str) -> str:
    """Get category for entity type."""
    for category, entities in ENTITY_CATEGORIES.items():
        if entity_type in entities:
            return category
    return "Other"


@router.get("", response_class=HTMLResponse, dependencies=[RequireMigrationRead])
async def migration_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    status_filter: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
):
    """Migration dashboard - list all jobs with stats."""
    per_page = 20

    # Build query
    query = db.query(MigrationJob).order_by(desc(MigrationJob.created_at))

    if status_filter:
        try:
            status_enum = MigrationStatus(status_filter)
            query = query.filter(MigrationJob.status == status_enum)
        except ValueError:
            pass

    # Get total and paginate
    total = query.count()
    jobs = query.offset((page - 1) * per_page).limit(per_page).all()

    # Calculate stats
    stats = {
        "total": db.query(func.count(MigrationJob.id)).scalar() or 0,
        "running": db.query(func.count(MigrationJob.id)).filter(
            MigrationJob.status == MigrationStatus.RUNNING
        ).scalar() or 0,
        "completed": db.query(func.count(MigrationJob.id)).filter(
            MigrationJob.status == MigrationStatus.COMPLETED
        ).scalar() or 0,
        "failed": db.query(func.count(MigrationJob.id)).filter(
            MigrationJob.status == MigrationStatus.FAILED
        ).scalar() or 0,
    }

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Data Migration"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Migration"},
    ])
    context["settings_nav"] = get_settings_nav(user, "migration")
    context["jobs"] = jobs
    context["stats"] = stats
    context["status_filter"] = status_filter
    context["status_colors"] = MIGRATION_STATUS_COLORS
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/settings/templates/pages/migration/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireMigrationWrite])
async def new_job_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New migration job form."""
    # Get entity types from registry with full metadata
    entities_from_registry = list_entities()
    entity_types = []
    for entity in entities_from_registry:
        entity_types.append({
            "value": entity["type"],
            "label": entity["display_name"],
            "description": entity.get("description", ""),
            "category": get_entity_category(entity["type"]),
            "dependencies": entity.get("dependencies", []),
        })

    # Get recommended migration order
    migration_order = get_migration_order()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Migration Job"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Migration", "href": "/settings/migration"},
        {"label": "New Job"},
    ])
    context["settings_nav"] = get_settings_nav(user, "migration")
    context["entity_types"] = entity_types
    context["categories"] = list(ENTITY_CATEGORIES.keys())
    context["migration_order"] = migration_order

    template = templates.get_template("modules/settings/templates/pages/migration/new_job.html")
    return HTMLResponse(template.render(context))


@router.post("/new", response_class=HTMLResponse, dependencies=[RequireMigrationWrite])
async def create_job(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new migration job using MigrationService."""
    form = await request.form()
    raw_name = form.get("name", "")
    name = raw_name if isinstance(raw_name, str) else ""
    name = name.strip()
    raw_entity_type = form.get("entity_type", "")
    entity_type_str = raw_entity_type if isinstance(raw_entity_type, str) else ""
    entity_type_str = entity_type_str.strip()

    # Validate
    if not name:
        set_flash(response, "Job name is required.", "error")
        return RedirectResponse(url="/settings/migration/new", status_code=303)

    if not entity_type_str:
        set_flash(response, "Entity type is required.", "error")
        return RedirectResponse(url="/settings/migration/new", status_code=303)

    # Use service to create job
    try:
        service = MigrationService(db, user_id=user.id)
        job = service.create_job(name, entity_type_str)
    except ValueError as e:
        set_flash(response, str(e), "error")
        return RedirectResponse(url="/settings/migration/new", status_code=303)

    # Check for dependency warnings
    deps = get_dependencies(entity_type_str)
    if deps:
        dep_names = ", ".join([get_entity_display_name(d) for d in deps])
        set_flash(response, f"Migration job '{name}' created. Note: This entity depends on {dep_names}.", "success")
    else:
        set_flash(response, f"Migration job '{name}' created. Upload a file to continue.", "success")

    return RedirectResponse(url=f"/settings/migration/jobs/{job.id}", status_code=303)


@router.get("/jobs/{job_id}", response_class=HTMLResponse, dependencies=[RequireMigrationRead])
async def job_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
):
    """Job detail page with workflow steps."""
    job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Determine current step
    step_map = {
        MigrationStatus.PENDING: 1,
        MigrationStatus.UPLOADED: 2,
        MigrationStatus.MAPPED: 3,
        MigrationStatus.VALIDATING: 4,
        MigrationStatus.VALIDATED: 4,
        MigrationStatus.RUNNING: 5,
        MigrationStatus.COMPLETED: 6,
        MigrationStatus.FAILED: 5,
        MigrationStatus.CANCELLED: 5,
        MigrationStatus.ROLLED_BACK: 6,
    }
    current_step = step_map.get(job.status, 1)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = job.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Migration", "href": "/settings/migration"},
        {"label": job.name},
    ])
    context["settings_nav"] = get_settings_nav(user, "migration")
    context["job"] = job
    context["current_step"] = current_step
    context["status_colors"] = MIGRATION_STATUS_COLORS

    template = templates.get_template("modules/settings/templates/pages/migration/job_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/jobs/{job_id}/upload", response_class=HTMLResponse, dependencies=[RequireMigrationWrite])
async def upload_file(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
    file: UploadFile = File(...),
):
    """Handle file upload using MigrationService."""
    # Validate file
    if not file.filename:
        set_flash(response, "No file provided.", "error")
        return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)

    # Read file content
    content = await file.read()
    if not content:
        set_flash(response, "File is empty.", "error")
        return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)

    # Use service to handle upload and parsing
    try:
        service = MigrationService(db, user_id=user.id)
        job = service.upload_file(job_id, content, file.filename)
        set_flash(response, f"File uploaded successfully. {job.total_rows:,} rows found.", "success")
    except ValueError as e:
        set_flash(response, str(e), "error")

    return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)


@router.get("/jobs/{job_id}/mapping", response_class=HTMLResponse, dependencies=[RequireMigrationRead])
async def mapping_page(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
):
    """Field mapping editor using registry for schema."""
    service = MigrationService(db, user_id=user.id)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in [MigrationStatus.UPLOADED, MigrationStatus.MAPPED]:
        set_flash(response, "Cannot edit mapping in current status.", "error")
        return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)

    # Get target field schema from registry
    entity_config = get_entity_config(job.entity_type.value)
    fields_config = get_entity_fields(job.entity_type.value)

    target_fields = []
    for name, cfg in fields_config.items():
        field_type = cfg.get("type", "string")
        if hasattr(field_type, "value"):
            field_type = field_type.value
        target_fields.append({
            "name": name,
            "type": str(field_type),
            "required": cfg.get("required", False),
            "unique": cfg.get("unique", False),
            "description": cfg.get("description", ""),
            "enum_values": cfg.get("enum_values", []),
        })

    # Get auto-suggestions from service
    suggestions = {}
    if not job.field_mapping and job.source_columns:
        suggestions = service.suggest_mapping(job_id)

    # Cleaning rule options
    cleaning_rules_options = [
        {"key": "trim", "label": "Trim whitespace", "description": "Remove leading/trailing spaces"},
        {"key": "lowercase", "label": "Lowercase", "description": "Convert to lowercase"},
        {"key": "uppercase", "label": "Uppercase", "description": "Convert to uppercase"},
        {"key": "titlecase", "label": "Title Case", "description": "Capitalize first letter of each word"},
        {"key": "remove_duplicates", "label": "Remove duplicate spaces", "description": "Collapse multiple spaces"},
        {"key": "normalize_phone", "label": "Normalize phone", "description": "Format phone numbers"},
        {"key": "normalize_email", "label": "Normalize email", "description": "Lowercase and validate emails"},
    ]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Field Mapping - {job.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Migration", "href": "/settings/migration"},
        {"label": job.name, "href": f"/settings/migration/jobs/{job_id}"},
        {"label": "Field Mapping"},
    ])
    context["settings_nav"] = get_settings_nav(user, "migration")
    context["job"] = job
    context["target_fields"] = target_fields
    context["suggestions"] = suggestions
    context["cleaning_rules_options"] = cleaning_rules_options
    context["dedup_strategies"] = [
        {"value": "skip", "label": "Skip duplicates"},
        {"value": "update", "label": "Update existing"},
        {"value": "merge", "label": "Merge data"},
    ]

    template = templates.get_template("modules/settings/templates/pages/migration/mapping.html")
    return HTMLResponse(template.render(context))


@router.post("/jobs/{job_id}/mapping", response_class=HTMLResponse, dependencies=[RequireMigrationWrite])
async def save_mapping(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    job_id: int,
):
    """Save field mapping configuration using MigrationService."""
    form = await request.form()

    # Parse field mapping from form
    field_mapping: dict[str, str] = {}
    for key, value in form.items():
        if key.startswith("mapping_") and isinstance(value, str) and value:
            source_col = key[8:]  # Remove "mapping_" prefix
            field_mapping[source_col] = value

    # Parse dedup settings
    raw_dedup_strategy = form.get("dedup_strategy", "skip")
    dedup_strategy_str = raw_dedup_strategy if isinstance(raw_dedup_strategy, str) else "skip"
    dedup_fields = [
        value for value in form.getlist("dedup_fields")
        if isinstance(value, str) and value
    ] or None

    # Parse cleaning rules from form
    cleaning_rules: dict[str, list[str]] = {}
    cleaning_keys = [
        value for value in form.getlist("cleaning_rules")
        if isinstance(value, str) and value
    ]
    if cleaning_keys:
        cleaning_rules = {
            "global": list(cleaning_keys)
        }
        # Check for field-specific cleaning rules
        for key, value in form.items():
            if key.startswith("cleaning_field_") and isinstance(value, str) and value:
                field_name = key[15:]  # Remove "cleaning_field_" prefix
                if field_name not in cleaning_rules:
                    cleaning_rules[field_name] = []
                cleaning_rules[field_name].extend(
                    v for v in form.getlist(key) if isinstance(v, str) and v
                )

    # Use service to save mapping
    try:
        service = MigrationService(db, user_id=user.id)
        service.save_mapping(
            job_id,
            field_mapping,
            cleaning_rules if cleaning_rules else None,
            dedup_strategy_str,
            dedup_fields
        )
        set_flash(response, "Field mapping saved successfully.", "success")
    except ValueError as e:
        set_flash(response, str(e), "error")

    return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)


@router.post("/jobs/{job_id}/validate", response_class=HTMLResponse, dependencies=[RequireMigrationWrite])
async def run_validation(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
):
    """Run validation using MigrationService."""
    try:
        service = MigrationService(db, user_id=user.id)
        result = service.validate(job_id)

        if result.is_valid:
            set_flash(response, f"Validation passed. {result.warning_count} warnings.", "success")
        else:
            set_flash(response, f"Validation failed. {result.error_count} errors, {result.warning_count} warnings.", "error")
    except ValueError as e:
        set_flash(response, str(e), "error")

    return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)


@router.post("/jobs/{job_id}/execute", response_class=HTMLResponse, dependencies=[RequireMigrationWrite])
async def execute_migration(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
):
    """Execute migration using MigrationService."""
    try:
        service = MigrationService(db, user_id=user.id)
        service.execute(job_id)

        # Get final stats
        progress = service.get_progress(job_id)
        created = progress.get("created_records", 0)
        updated = progress.get("updated_records", 0)
        failed = progress.get("failed_records", 0)

        if failed > 0:
            set_flash(response, f"Migration completed with {failed} failures. Created: {created}, Updated: {updated}.", "warning")
        else:
            set_flash(response, f"Migration completed successfully. Created: {created}, Updated: {updated}.", "success")
    except ValueError as e:
        set_flash(response, str(e), "error")

    return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)


@router.get("/jobs/{job_id}/progress", response_class=HTMLResponse, dependencies=[RequireMigrationRead])
async def get_progress(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
):
    """Get progress partial for HTMX polling."""
    job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    context = get_base_context(request, response, user, csrf_token)
    context["job"] = job
    context["status_colors"] = MIGRATION_STATUS_COLORS

    template = templates.get_template("modules/settings/templates/partials/migration/progress.html")
    return HTMLResponse(template.render(context))


@router.get("/jobs/{job_id}/records", response_class=HTMLResponse, dependencies=[RequireMigrationRead])
async def records_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
):
    """Records list for a migration job."""
    job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    per_page = 50

    # Build query
    query = db.query(MigrationRecord).filter(
        MigrationRecord.job_id == job_id
    ).order_by(MigrationRecord.row_number)

    if action:
        try:
            action_enum = RecordAction(action)
            query = query.filter(MigrationRecord.action == action_enum)
        except ValueError:
            pass

    # Get total and paginate
    total = query.count()
    records = query.offset((page - 1) * per_page).limit(per_page).all()

    # Get action counts
    action_counts = {
        "created": db.query(func.count(MigrationRecord.id)).filter(
            MigrationRecord.job_id == job_id,
            MigrationRecord.action == RecordAction.CREATED
        ).scalar() or 0,
        "updated": db.query(func.count(MigrationRecord.id)).filter(
            MigrationRecord.job_id == job_id,
            MigrationRecord.action == RecordAction.UPDATED
        ).scalar() or 0,
        "skipped": db.query(func.count(MigrationRecord.id)).filter(
            MigrationRecord.job_id == job_id,
            MigrationRecord.action == RecordAction.SKIPPED
        ).scalar() or 0,
        "failed": db.query(func.count(MigrationRecord.id)).filter(
            MigrationRecord.job_id == job_id,
            MigrationRecord.action == RecordAction.FAILED
        ).scalar() or 0,
    }

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Records - {job.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Migration", "href": "/settings/migration"},
        {"label": job.name, "href": f"/settings/migration/jobs/{job_id}"},
        {"label": "Records"},
    ])
    context["settings_nav"] = get_settings_nav(user, "migration")
    context["job"] = job
    context["records"] = records
    context["action_filter"] = action
    context["action_counts"] = action_counts
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/settings/templates/partials/migration/records_table.html")
    else:
        template = templates.get_template("modules/settings/templates/pages/migration/records.html")

    return HTMLResponse(template.render(context))


@router.post("/jobs/{job_id}/cancel", response_class=HTMLResponse, dependencies=[RequireMigrationWrite])
async def cancel_job(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
):
    """Cancel a running migration job."""
    job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != MigrationStatus.RUNNING:
        set_flash(response, "Can only cancel running jobs.", "error")
        return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)

    # Cancel the job
    job.status = MigrationStatus.CANCELLED
    job.error_message = "Cancelled by user"
    job.completed_at = utc_now()
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Migration job cancelled.", "success")
        response.headers["HX-Refresh"] = "true"
        return HTMLResponse("")

    set_flash(response, "Migration job cancelled.", "success")
    return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)


@router.get("/jobs/{job_id}/rollback-preview", response_class=HTMLResponse, dependencies=[RequireMigrationRead])
async def rollback_preview(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
):
    """Preview rollback for a completed migration job."""
    job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != MigrationStatus.COMPLETED:
        set_flash(response, "Can only rollback completed jobs.", "error")
        return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)

    # Get records that would be affected by rollback
    created_records = db.query(MigrationRecord).filter(
        MigrationRecord.job_id == job_id,
        MigrationRecord.action == RecordAction.CREATED
    ).count()

    updated_records = db.query(MigrationRecord).filter(
        MigrationRecord.job_id == job_id,
        MigrationRecord.action == RecordAction.UPDATED
    ).count()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Rollback Preview - {job.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Migration", "href": "/settings/migration"},
        {"label": job.name, "href": f"/settings/migration/jobs/{job_id}"},
        {"label": "Rollback Preview"},
    ])
    context["settings_nav"] = get_settings_nav(user, "migration")
    context["job"] = job
    context["created_count"] = created_records
    context["updated_count"] = updated_records
    context["status_colors"] = MIGRATION_STATUS_COLORS

    template = templates.get_template("modules/settings/templates/pages/migration/rollback_preview.html")
    return HTMLResponse(template.render(context))


@router.post("/jobs/{job_id}/rollback", response_class=HTMLResponse, dependencies=[RequireMigrationWrite])
async def execute_rollback(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    job_id: int,
):
    """Execute rollback using MigrationService."""
    try:
        service = MigrationService(db, user_id=user.id)
        result = service.rollback(job_id)

        deleted = result.get("deleted_records", 0)
        restored = result.get("restored_records", 0)
        set_flash(response, f"Migration rolled back. Deleted: {deleted}, Restored: {restored}.", "success")
    except ValueError as e:
        set_flash(response, str(e), "error")

    return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)


@router.get("/jobs/{job_id}/preview", response_class=HTMLResponse, dependencies=[RequireMigrationRead])
async def preview_page(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
    page: int = Query(1, ge=1),
):
    """Preview transformed data using MigrationService."""
    service = MigrationService(db, user_id=user.id)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in [MigrationStatus.MAPPED, MigrationStatus.VALIDATED]:
        set_flash(response, "Cannot preview in current status.", "error")
        return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)

    # Get preview from service
    per_page = 20
    offset = (page - 1) * per_page
    try:
        preview_rows = service.get_preview(job_id, limit=per_page, offset=offset)
    except ValueError:
        preview_rows = []

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Data Preview - {job.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Migration", "href": "/settings/migration"},
        {"label": job.name, "href": f"/settings/migration/jobs/{job_id}"},
        {"label": "Preview"},
    ])
    context["settings_nav"] = get_settings_nav(user, "migration")
    context["job"] = job
    context["preview_rows"] = preview_rows
    context["status_colors"] = MIGRATION_STATUS_COLORS

    template = templates.get_template("modules/settings/templates/pages/migration/preview.html")
    return HTMLResponse(template.render(context))


@router.get("/jobs/{job_id}/duplicates", response_class=HTMLResponse, dependencies=[RequireMigrationRead])
async def duplicates_report(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
    page: int = Query(1, ge=1),
):
    """View duplicate records found during migration."""
    job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    per_page = 50

    # Get skipped records (duplicates)
    query = db.query(MigrationRecord).filter(
        MigrationRecord.job_id == job_id,
        MigrationRecord.action == RecordAction.SKIPPED
    ).order_by(MigrationRecord.row_number)

    total = query.count()
    duplicates = query.offset((page - 1) * per_page).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Duplicates - {job.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Data Migration", "href": "/settings/migration"},
        {"label": job.name, "href": f"/settings/migration/jobs/{job_id}"},
        {"label": "Duplicates"},
    ])
    context["settings_nav"] = get_settings_nav(user, "migration")
    context["job"] = job
    context["duplicates"] = duplicates
    context["pagination"] = build_pagination_context(page, per_page, total)
    context["status_colors"] = MIGRATION_STATUS_COLORS

    template = templates.get_template("modules/settings/templates/pages/migration/duplicates.html")
    return HTMLResponse(template.render(context))


@router.delete("/jobs/{job_id}", response_class=HTMLResponse, dependencies=[RequireMigrationWrite])
async def delete_job(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    job_id: int,
):
    """Delete a migration job."""
    job = db.query(MigrationJob).filter(MigrationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == MigrationStatus.RUNNING:
        if is_htmx_request(request):
            htmx_toast(response, "Cannot delete a running job.", "error")
            return HTMLResponse("")
        set_flash(response, "Cannot delete a running job.", "error")
        return RedirectResponse(url=f"/settings/migration/jobs/{job_id}", status_code=303)

    # Delete file if exists
    if job.source_file_path and os.path.exists(job.source_file_path):
        os.remove(job.source_file_path)

    # Delete job (cascades to records)
    db.delete(job)
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Migration job deleted.", "success")
        response.headers["HX-Redirect"] = "/settings/migration"
        return HTMLResponse("")

    set_flash(response, "Migration job deleted.", "success")
    return RedirectResponse(url="/settings/migration", status_code=303)
