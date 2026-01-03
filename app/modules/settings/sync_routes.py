"""
Sync Management Routes - Manage Splynx, ERPNext, and Chatwoot sync operations.

Permission Requirements:
- settings:sync - View and manage sync settings
"""
from __future__ import annotations

from typing import Optional, TypedDict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.sync_log import SyncLog, SyncStatus, SyncSource
from app.models.sync_cursor import SyncCursor, FailedSyncRecord
from app.models.sync_schedule import SyncSchedule
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.modules.settings.routes import get_settings_nav
from app.utils.datetime_utils import utc_now

# Permission dependencies
RequireSyncRead = Depends(require_scope("settings:sync"))
RequireSyncWrite = Depends(require_scope("settings:sync"))

router = APIRouter(prefix="/sync", tags=["settings-sync"])
templates = get_template_env()


class SyncEntity(TypedDict):
    id: str
    label: str
    icon: str
    category: str


class SyncSourceConfig(TypedDict):
    source: SyncSource
    label: str
    description: str
    entities: list[SyncEntity]


# Define all synced entities with metadata
SYNC_ENTITIES: dict[str, SyncSourceConfig] = {
    "splynx": {
        "source": SyncSource.SPLYNX,
        "label": "Splynx",
        "description": "ISP billing and customer management",
        "entities": [
            {"id": "customers", "label": "Customers", "icon": "users", "category": "CRM"},
            {"id": "leads", "label": "Leads", "icon": "user-plus", "category": "CRM"},
            {"id": "customer_notes", "label": "Customer Notes", "icon": "file-text", "category": "CRM"},
            {"id": "services", "label": "Services (Subscriptions)", "icon": "wifi", "category": "Services"},
            {"id": "tariffs", "label": "Tariffs", "icon": "tag", "category": "Services"},
            {"id": "usage", "label": "Usage Data", "icon": "activity", "category": "Services"},
            {"id": "invoices", "label": "Invoices", "icon": "file-text", "category": "Billing"},
            {"id": "payments", "label": "Payments", "icon": "credit-card", "category": "Billing"},
            {"id": "credit_notes", "label": "Credit Notes", "icon": "file-minus", "category": "Billing"},
            {"id": "payment_methods", "label": "Payment Methods", "icon": "credit-card", "category": "Billing"},
            {"id": "transaction_categories", "label": "Transaction Categories", "icon": "folder", "category": "Billing"},
            {"id": "locations", "label": "Locations (POPs)", "icon": "map-pin", "category": "Network"},
            {"id": "routers", "label": "Routers", "icon": "server", "category": "Network"},
            {"id": "ipv4_networks", "label": "IPv4 Networks", "icon": "globe", "category": "Network"},
            {"id": "ipv4_addresses", "label": "IPv4 Addresses", "icon": "hash", "category": "Network"},
            {"id": "ipv6_networks", "label": "IPv6 Networks", "icon": "globe", "category": "Network"},
            {"id": "network_monitors", "label": "Network Monitors", "icon": "monitor", "category": "Network"},
            {"id": "tickets", "label": "Tickets", "icon": "message-square", "category": "Support"},
            {"id": "ticket_messages", "label": "Ticket Messages", "icon": "message-circle", "category": "Support"},
            {"id": "administrators", "label": "Administrators", "icon": "user-check", "category": "Admin"},
        ],
    },
    "erpnext": {
        "source": SyncSource.ERPNEXT,
        "label": "ERPNext",
        "description": "Enterprise resource planning",
        "entities": [
            # Sales
            {"id": "customers", "label": "Customers", "icon": "users", "category": "Sales"},
            {"id": "leads", "label": "Leads", "icon": "user-plus", "category": "Sales"},
            {"id": "quotations", "label": "Quotations", "icon": "file-text", "category": "Sales"},
            {"id": "sales_orders", "label": "Sales Orders", "icon": "shopping-cart", "category": "Sales"},
            # Accounting
            {"id": "invoices", "label": "Sales Invoices", "icon": "file-text", "category": "Accounting"},
            {"id": "payments", "label": "Payments", "icon": "credit-card", "category": "Accounting"},
            {"id": "expenses", "label": "Expense Claims", "icon": "receipt", "category": "Accounting"},
            {"id": "journal_entries", "label": "Journal Entries", "icon": "book", "category": "Accounting"},
            {"id": "suppliers", "label": "Suppliers", "icon": "truck", "category": "Accounting"},
            # HR
            {"id": "employees", "label": "Employees", "icon": "users", "category": "HR"},
            {"id": "departments", "label": "Departments", "icon": "briefcase", "category": "HR"},
            # Inventory
            {"id": "items", "label": "Items", "icon": "box", "category": "Inventory"},
            # Support
            {"id": "hd_tickets", "label": "HD Tickets", "icon": "message-square", "category": "Support"},
        ],
    },
    "chatwoot": {
        "source": SyncSource.CHATWOOT,
        "label": "Chatwoot",
        "description": "Customer conversations and messaging",
        "entities": [
            {"id": "conversations", "label": "Conversations", "icon": "message-circle", "category": "Messaging"},
            {"id": "contacts", "label": "Contacts", "icon": "users", "category": "Messaging"},
            {"id": "messages", "label": "Messages", "icon": "mail", "category": "Messaging"},
        ],
    },
}


def get_entity_stats(db: Session, source: SyncSource, entity_type: str) -> dict:
    """Get stats for a specific entity type."""
    # Get cursor
    cursor = db.query(SyncCursor).filter(
        SyncCursor.source == source,
        SyncCursor.entity_type == entity_type,
    ).first()

    # Get last sync log
    last_log = db.query(SyncLog).filter(
        SyncLog.source == source,
        SyncLog.entity_type == entity_type,
    ).order_by(desc(SyncLog.started_at)).first()

    # Get recent failure count (last 24 hours)
    yesterday = utc_now() - timedelta(hours=24)
    recent_failures = db.query(func.count(SyncLog.id)).filter(
        SyncLog.source == source,
        SyncLog.entity_type == entity_type,
        SyncLog.status == SyncStatus.FAILED,
        SyncLog.started_at >= yesterday,
    ).scalar() or 0

    # Get failed records count
    failed_records = db.query(func.count(FailedSyncRecord.id)).filter(
        FailedSyncRecord.source == source,
        FailedSyncRecord.entity_type == entity_type,
        FailedSyncRecord.is_resolved == False,
    ).scalar() or 0

    return {
        "cursor": cursor,
        "last_log": last_log,
        "recent_failures": recent_failures,
        "failed_records": failed_records,
        "last_sync_at": cursor.last_sync_at if cursor else None,
        "records_synced": cursor.records_synced if cursor else 0,
    }


def get_overall_stats(db: Session) -> dict:
    """Get overall sync statistics."""
    yesterday = utc_now() - timedelta(hours=24)

    # Total syncs in last 24 hours
    total_syncs = db.query(func.count(SyncLog.id)).filter(
        SyncLog.started_at >= yesterday,
    ).scalar() or 0

    # Successful syncs
    successful_syncs = db.query(func.count(SyncLog.id)).filter(
        SyncLog.started_at >= yesterday,
        SyncLog.status == SyncStatus.COMPLETED,
    ).scalar() or 0

    # Failed syncs
    failed_syncs = db.query(func.count(SyncLog.id)).filter(
        SyncLog.started_at >= yesterday,
        SyncLog.status == SyncStatus.FAILED,
    ).scalar() or 0

    # Records synced
    records_created = db.query(func.sum(SyncLog.records_created)).filter(
        SyncLog.started_at >= yesterday,
    ).scalar() or 0

    records_updated = db.query(func.sum(SyncLog.records_updated)).filter(
        SyncLog.started_at >= yesterday,
    ).scalar() or 0

    # Pending failed records
    pending_failures = db.query(func.count(FailedSyncRecord.id)).filter(
        FailedSyncRecord.is_resolved == False,
    ).scalar() or 0

    return {
        "total_syncs": total_syncs,
        "successful_syncs": successful_syncs,
        "failed_syncs": failed_syncs,
        "records_created": records_created,
        "records_updated": records_updated,
        "pending_failures": pending_failures,
        "success_rate": round((successful_syncs / total_syncs * 100) if total_syncs > 0 else 0, 1),
    }


# =============================================================================
# SYNC DASHBOARD
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequireSyncRead])
async def sync_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Sync management dashboard - overview of all sync sources and entities."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Sync Management"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Sync Management"},
    ])
    context["settings_nav"] = get_settings_nav(user, "sync")

    # Overall stats
    context["stats"] = get_overall_stats(db)

    # Build entity data with stats for each source
    sources_data = {}
    for source_key, source_config in SYNC_ENTITIES.items():
        entities_with_stats: list[dict[str, Any]] = []
        for entity in source_config["entities"]:
            entity_stats = get_entity_stats(db, source_config["source"], entity["id"])
            combined: dict[str, Any] = {**entity, **entity_stats}
            entities_with_stats.append(combined)

        # Group by category
        categories: dict[str, list[dict[str, Any]]] = {}
        for entity_item in entities_with_stats:
            cat = entity_item.get("category", "Other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(entity_item)

        sources_data[source_key] = {
            **source_config,
            "entities": entities_with_stats,
            "categories": categories,
        }

    context["sources"] = sources_data

    # Get recent sync logs
    recent_logs = db.query(SyncLog).order_by(
        desc(SyncLog.started_at)
    ).limit(10).all()
    context["recent_logs"] = recent_logs

    template = templates.get_template("modules/settings/templates/pages/sync/dashboard.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# ENTITY DETAIL
# =============================================================================

@router.get("/{source}/{entity_type}", response_class=HTMLResponse, dependencies=[RequireSyncRead])
async def sync_entity_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    source: str,
    entity_type: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Entity sync detail page with logs and stats."""
    if source not in SYNC_ENTITIES:
        raise HTTPException(status_code=404, detail="Unknown sync source")

    source_config = SYNC_ENTITIES[source]
    entity_config = next(
        (e for e in source_config["entities"] if e["id"] == entity_type),
        None
    )
    if not entity_config:
        raise HTTPException(status_code=404, detail="Unknown entity type")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"{entity_config['label']} Sync"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Sync Management", "href": "/settings/sync"},
        {"label": source_config["label"]},
        {"label": entity_config["label"]},
    ])
    context["settings_nav"] = get_settings_nav(user, "sync")

    context["source"] = source
    context["source_config"] = source_config
    context["entity_type"] = entity_type
    context["entity_config"] = entity_config

    # Get entity stats
    context["entity_stats"] = get_entity_stats(db, source_config["source"], entity_type)

    # Get sync cursor
    context["cursor"] = db.query(SyncCursor).filter(
        SyncCursor.source == source_config["source"],
        SyncCursor.entity_type == entity_type,
    ).first()

    # Get sync logs with pagination
    logs_query = db.query(SyncLog).filter(
        SyncLog.source == source_config["source"],
        SyncLog.entity_type == entity_type,
    ).order_by(desc(SyncLog.started_at))

    total = logs_query.count()
    offset = (page - 1) * per_page
    logs = logs_query.offset(offset).limit(per_page).all()

    context["logs"] = logs
    context["pagination"] = build_pagination_context(page, per_page, total)

    # Get failed records
    failed_records = db.query(FailedSyncRecord).filter(
        FailedSyncRecord.source == source_config["source"],
        FailedSyncRecord.entity_type == entity_type,
        FailedSyncRecord.is_resolved == False,
    ).order_by(desc(FailedSyncRecord.created_at)).limit(10).all()
    context["failed_records"] = failed_records

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/settings/templates/partials/sync_logs_table.html")
        return HTMLResponse(template.render(context))

    template = templates.get_template("modules/settings/templates/pages/sync/entity_detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{source}/{entity_type}/logs", response_class=HTMLResponse, dependencies=[RequireSyncRead])
async def sync_entity_logs(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    source: str,
    entity_type: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """HTMX endpoint for sync logs table."""
    return await sync_entity_detail(
        request, response, user, csrf_token, db,
        source, entity_type, page, per_page
    )


# =============================================================================
# SYNC ACTIONS
# =============================================================================

@router.post("/{source}/{entity_type}/run", response_class=HTMLResponse, dependencies=[RequireSyncWrite])
async def trigger_sync(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    source: str,
    entity_type: str,
):
    """Manually trigger a sync for an entity type."""
    if source not in SYNC_ENTITIES:
        raise HTTPException(status_code=404, detail="Unknown sync source")

    source_config = SYNC_ENTITIES[source]
    entity_config = next(
        (e for e in source_config["entities"] if e["id"] == entity_type),
        None
    )
    if not entity_config:
        raise HTTPException(status_code=404, detail="Unknown entity type")

    # Trigger the appropriate Celery task
    task_triggered = False
    task_name = f"sync_{source}_{entity_type}"

    try:
        from app.tasks import sync_tasks

        # Map entity types to Celery tasks
        task_map = {
            # Splynx tasks - CRM
            ("splynx", "customers"): sync_tasks.sync_splynx_customers,
            ("splynx", "leads"): sync_tasks.sync_splynx_leads,
            ("splynx", "customer_notes"): sync_tasks.sync_splynx_customer_notes,
            # Splynx tasks - Services
            ("splynx", "services"): sync_tasks.sync_splynx_services,
            ("splynx", "tariffs"): sync_tasks.sync_splynx_tariffs,
            ("splynx", "usage"): sync_tasks.sync_splynx_usage,
            # Splynx tasks - Billing
            ("splynx", "invoices"): sync_tasks.sync_splynx_invoices,
            ("splynx", "payments"): sync_tasks.sync_splynx_payments,
            ("splynx", "credit_notes"): sync_tasks.sync_splynx_credit_notes,
            ("splynx", "payment_methods"): sync_tasks.sync_splynx_payment_methods,
            ("splynx", "transaction_categories"): sync_tasks.sync_splynx_transaction_categories,
            # Splynx tasks - Network
            ("splynx", "locations"): sync_tasks.sync_splynx_locations,
            ("splynx", "routers"): sync_tasks.sync_splynx_routers,
            ("splynx", "ipv4_networks"): sync_tasks.sync_splynx_ipv4_networks,
            ("splynx", "ipv4_addresses"): sync_tasks.sync_splynx_ipv4_addresses,
            ("splynx", "ipv6_networks"): sync_tasks.sync_splynx_ipv6_networks,
            ("splynx", "network_monitors"): sync_tasks.sync_splynx_network_monitors,
            # Splynx tasks - Support
            ("splynx", "tickets"): sync_tasks.sync_splynx_tickets,
            ("splynx", "ticket_messages"): sync_tasks.sync_splynx_ticket_messages,
            # Splynx tasks - Admin
            ("splynx", "administrators"): sync_tasks.sync_splynx_administrators,
            # ERPNext tasks - HR
            ("erpnext", "employees"): sync_tasks.sync_erpnext_hr,
            ("erpnext", "departments"): sync_tasks.sync_erpnext_hr,
            # ERPNext tasks - Inventory
            ("erpnext", "items"): sync_tasks.sync_erpnext_items,
            # ERPNext tasks - Purchasing
            ("erpnext", "suppliers"): sync_tasks.sync_erpnext_extended_accounting,
            # ERPNext tasks - Accounting
            ("erpnext", "journal_entries"): sync_tasks.sync_erpnext_accounting,
            ("erpnext", "customers"): sync_tasks.sync_erpnext_customers,
            ("erpnext", "invoices"): sync_tasks.sync_erpnext_invoices,
            ("erpnext", "payments"): sync_tasks.sync_erpnext_payments,
            ("erpnext", "expenses"): sync_tasks.sync_erpnext_expenses,
            # ERPNext tasks - Support
            ("erpnext", "hd_tickets"): sync_tasks.sync_erpnext_hd_tickets,
            # ERPNext tasks - Sales
            ("erpnext", "sales_orders"): sync_tasks.sync_erpnext_sales,
            ("erpnext", "quotations"): sync_tasks.sync_erpnext_sales,
            ("erpnext", "leads"): sync_tasks.sync_erpnext_sales,
            # Chatwoot tasks
            ("chatwoot", "contacts"): sync_tasks.sync_chatwoot_contacts,
            ("chatwoot", "conversations"): sync_tasks.sync_chatwoot_conversations,
            ("chatwoot", "messages"): sync_tasks.sync_chatwoot_conversations,  # Messages synced with conversations
        }

        task = task_map.get((source, entity_type))
        if task:
            task.delay(full_sync=False)
            task_triggered = True
            message = f"Sync queued for {source_config['label']} {entity_config['label']}"
        else:
            message = f"No dedicated task for {entity_config['label']}. Use full sync instead."

    except ImportError as e:
        logger.warning("celery_import_failed", error=str(e))
        message = f"Sync service unavailable: {str(e)}"
    except Exception as e:
        logger.error("sync_trigger_failed", error=str(e), source=source, entity=entity_type)
        message = f"Failed to trigger sync: {str(e)}"

    toast_type = "success" if task_triggered else "warning"

    if is_htmx_request(request):
        htmx_toast(response, message, toast_type)
        response.headers["HX-Refresh"] = "true"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, message, toast_type)
    return HTMLResponse(
        "",
        status_code=303,
        headers={"Location": f"/settings/sync/{source}/{entity_type}"}
    )


@router.post("/{source}/{entity_type}/reset", response_class=HTMLResponse, dependencies=[RequireSyncWrite])
async def reset_sync_cursor(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    source: str,
    entity_type: str,
):
    """Reset sync cursor to trigger full re-sync."""
    if source not in SYNC_ENTITIES:
        raise HTTPException(status_code=404, detail="Unknown sync source")

    source_config = SYNC_ENTITIES[source]

    cursor = db.query(SyncCursor).filter(
        SyncCursor.source == source_config["source"],
        SyncCursor.entity_type == entity_type,
    ).first()

    if cursor:
        cursor.reset()
        db.commit()
        message = f"Cursor reset for {entity_type}. Next sync will be a full sync."
    else:
        message = f"No cursor found for {entity_type}."

    if is_htmx_request(request):
        htmx_toast(response, message, "success" if cursor else "warning")
        response.headers["HX-Refresh"] = "true"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, message, "success" if cursor else "warning")
    return HTMLResponse(
        "",
        status_code=303,
        headers={"Location": f"/settings/sync/{source}/{entity_type}"}
    )


# =============================================================================
# FAILED RECORDS
# =============================================================================

@router.post("/failed-records/{record_id}/retry", response_class=HTMLResponse, dependencies=[RequireSyncWrite])
async def retry_failed_record(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    record_id: int,
):
    """Retry a failed sync record."""
    record = db.query(FailedSyncRecord).filter(
        FailedSyncRecord.id == record_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Failed record not found")

    if not record.can_retry:
        raise HTTPException(status_code=400, detail="Record cannot be retried")

    record.mark_retry()
    db.commit()

    message = f"Retry queued for record {record.external_id or record_id}"

    if is_htmx_request(request):
        htmx_toast(response, message, "info")
        response.headers["HX-Refresh"] = "true"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, message, "info")
    return HTMLResponse("", status_code=303, headers={"Location": request.headers.get("Referer", "/settings/sync")})


@router.post("/failed-records/{record_id}/resolve", response_class=HTMLResponse, dependencies=[RequireSyncWrite])
async def resolve_failed_record(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    record_id: int,
):
    """Mark a failed sync record as resolved."""
    record = db.query(FailedSyncRecord).filter(
        FailedSyncRecord.id == record_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Failed record not found")

    form = await request.form()
    raw_notes = form.get("notes", "")
    notes = raw_notes if isinstance(raw_notes, str) else ""
    notes = notes.strip()

    record.mark_resolved(notes or "Manually resolved")
    db.commit()

    message = f"Record {record.external_id or record_id} marked as resolved"

    if is_htmx_request(request):
        htmx_toast(response, message, "success")
        response.headers["HX-Refresh"] = "true"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, message, "success")
    return HTMLResponse("", status_code=303, headers={"Location": request.headers.get("Referer", "/settings/sync")})


# =============================================================================
# SYNC SCHEDULES
# =============================================================================

@router.get("/schedules", response_class=HTMLResponse, dependencies=[RequireSyncRead])
async def sync_schedules_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """List all sync schedules."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Sync Schedules"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Settings", "href": "/settings"},
        {"label": "Sync Management", "href": "/settings/sync"},
        {"label": "Schedules"},
    ])
    context["settings_nav"] = get_settings_nav(user, "sync")

    schedules = db.query(SyncSchedule).order_by(
        SyncSchedule.is_system.desc(),
        SyncSchedule.name
    ).all()
    context["schedules"] = schedules

    template = templates.get_template("modules/settings/templates/pages/sync/schedules.html")
    return HTMLResponse(template.render(context))


@router.patch("/schedules/{schedule_id}/toggle", response_class=HTMLResponse, dependencies=[RequireSyncWrite])
async def toggle_schedule(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    schedule_id: int,
):
    """Toggle a sync schedule on/off."""
    schedule = db.query(SyncSchedule).filter(
        SyncSchedule.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    schedule.is_enabled = not schedule.is_enabled
    db.commit()

    status = "enabled" if schedule.is_enabled else "disabled"
    message = f"Schedule '{schedule.name}' {status}"

    if is_htmx_request(request):
        htmx_toast(response, message, "success")
        response.headers["HX-Refresh"] = "true"
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, message, "success")
    return HTMLResponse("", status_code=303, headers={"Location": "/settings/sync/schedules"})
