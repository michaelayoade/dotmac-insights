"""
Inventory Routes - Warehouse and Stock Management with SSR + HTMX.

Permission Requirements:
- inventory:read - View warehouses and stock entries
- inventory:write - Create, update, delete inventory items
"""
from __future__ import annotations

from typing import Optional, Any

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.inventory import Warehouse, StockEntry, StockEntryType
from app.core.security import is_htmx_request, htmx_toast, set_flash

# Permission dependencies
RequireInventoryRead = Depends(require_scope("inventory:read"))
RequireInventoryWrite = Depends(require_scope("inventory:write"))

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = get_template_env()


def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def get_warehouse_type_options():
    """Get warehouse type options."""
    return [
        {"value": "stores", "label": "Stores"},
        {"value": "transit", "label": "Transit"},
        {"value": "scrap", "label": "Scrap"},
        {"value": "manufacturing", "label": "Manufacturing"},
    ]


def get_stock_entry_type_options():
    """Get stock entry type options for select dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in StockEntryType
    ]


# =============================================================================
# WAREHOUSE ROUTES
# =============================================================================

@router.get("", response_class=HTMLResponse, dependencies=[RequireInventoryRead])
async def warehouses_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    type: Optional[str] = Query(None, description="Filter by warehouse type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("warehouse_name", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Warehouse list page."""
    query = db.query(Warehouse).filter(Warehouse.is_deleted == False)

    # Search
    if q:
        search_filter = or_(
            Warehouse.warehouse_name.ilike(f"%{q}%"),
            Warehouse.warehouse_type.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if type:
        query = query.filter(Warehouse.warehouse_type == type)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(Warehouse, sort, Warehouse.warehouse_name)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    warehouses = query.offset(offset).limit(per_page).all()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["warehouses"] = warehouses
    context["search_query"] = q or ""
    context["current_type"] = type
    context["type_options"] = get_warehouse_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/inventory/templates/partials/warehouses_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Inventory"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Inventory"},
    ])

    template = templates.get_template("modules/inventory/templates/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireInventoryRead])
async def warehouses_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("warehouse_name"),
    dir: str = Query("asc"),
):
    """Warehouse table partial for HTMX updates."""
    return await warehouses_list(
        request, response, user, csrf_token, db,
        q, type, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def warehouse_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New warehouse form page."""
    # Get parent warehouse options
    parent_warehouses = db.query(Warehouse).filter(
        Warehouse.is_group == True,
        Warehouse.is_deleted == False,
    ).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Warehouse"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Inventory", "href": "/inventory"},
        {"label": "New Warehouse"},
    ])
    context["warehouse"] = None
    context["type_options"] = get_warehouse_type_options()
    context["parent_warehouses"] = parent_warehouses
    context["errors"] = {}

    template = templates.get_template("modules/inventory/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def warehouse_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new warehouse."""
    form = await request.form()

    # Basic validation
    errors = {}
    warehouse_name = _form_str(form, "warehouse_name")

    if not warehouse_name:
        errors["warehouse_name"] = "Warehouse name is required"

    # Check for duplicate name
    existing = db.query(Warehouse).filter(
        Warehouse.warehouse_name == warehouse_name,
        Warehouse.is_deleted == False,
    ).first()
    if existing:
        errors["warehouse_name"] = "A warehouse with this name already exists"

    if errors:
        parent_warehouses = db.query(Warehouse).filter(
            Warehouse.is_group == True,
            Warehouse.is_deleted == False,
        ).all()

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Warehouse"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Inventory", "href": "/inventory"},
            {"label": "New Warehouse"},
        ])
        context["warehouse"] = None
        context["type_options"] = get_warehouse_type_options()
        context["parent_warehouses"] = parent_warehouses
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/inventory/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Create warehouse
    warehouse = Warehouse(
        warehouse_name=warehouse_name,
        warehouse_type=_form_str(form, "warehouse_type") or None,
        parent_warehouse=_form_str(form, "parent_warehouse") or None,
        is_group=form.get("is_group") == "on",
        company=_form_str(form, "company") or None,
        origin_system="local",
    )
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)

    set_flash(response, f"Warehouse '{warehouse.warehouse_name}' created successfully.", "success")
    return RedirectResponse(url=f"/inventory/{warehouse.id}", status_code=303)


@router.get("/{warehouse_id}", response_class=HTMLResponse, dependencies=[RequireInventoryRead])
async def warehouse_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    warehouse_id: int,
):
    """Warehouse detail page."""
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id,
        Warehouse.is_deleted == False,
    ).first()

    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = warehouse.warehouse_name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Inventory", "href": "/inventory"},
        {"label": warehouse.warehouse_name},
    ])
    context["warehouse"] = warehouse

    template = templates.get_template("modules/inventory/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{warehouse_id}/edit", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def warehouse_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    warehouse_id: int,
):
    """Warehouse edit form page."""
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id,
        Warehouse.is_deleted == False,
    ).first()

    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    parent_warehouses = db.query(Warehouse).filter(
        Warehouse.is_group == True,
        Warehouse.is_deleted == False,
        Warehouse.id != warehouse_id,
    ).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {warehouse.warehouse_name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Inventory", "href": "/inventory"},
        {"label": warehouse.warehouse_name, "href": f"/inventory/{warehouse.id}"},
        {"label": "Edit"},
    ])
    context["warehouse"] = warehouse
    context["type_options"] = get_warehouse_type_options()
    context["parent_warehouses"] = parent_warehouses
    context["errors"] = {}

    template = templates.get_template("modules/inventory/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{warehouse_id}", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def warehouse_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    warehouse_id: int,
):
    """Update a warehouse."""
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id,
        Warehouse.is_deleted == False,
    ).first()

    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    form = await request.form()

    # Basic validation
    errors = {}
    warehouse_name = _form_str(form, "warehouse_name")

    if not warehouse_name:
        errors["warehouse_name"] = "Warehouse name is required"

    # Check for duplicate name (excluding current)
    existing = db.query(Warehouse).filter(
        Warehouse.warehouse_name == warehouse_name,
        Warehouse.is_deleted == False,
        Warehouse.id != warehouse_id,
    ).first()
    if existing:
        errors["warehouse_name"] = "A warehouse with this name already exists"

    if errors:
        parent_warehouses = db.query(Warehouse).filter(
            Warehouse.is_group == True,
            Warehouse.is_deleted == False,
            Warehouse.id != warehouse_id,
        ).all()

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {warehouse.warehouse_name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Inventory", "href": "/inventory"},
            {"label": warehouse.warehouse_name, "href": f"/inventory/{warehouse.id}"},
            {"label": "Edit"},
        ])
        context["warehouse"] = warehouse
        context["type_options"] = get_warehouse_type_options()
        context["parent_warehouses"] = parent_warehouses
        context["errors"] = errors

        template = templates.get_template("modules/inventory/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Update warehouse
    warehouse.warehouse_name = warehouse_name
    warehouse.warehouse_type = _form_str(form, "warehouse_type") or None
    warehouse.parent_warehouse = _form_str(form, "parent_warehouse") or None
    warehouse.is_group = form.get("is_group") == "on"
    warehouse.company = _form_str(form, "company") or None
    db.commit()

    set_flash(response, f"Warehouse '{warehouse.warehouse_name}' updated successfully.", "success")
    return RedirectResponse(url=f"/inventory/{warehouse.id}", status_code=303)


@router.delete("/{warehouse_id}", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def warehouse_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    warehouse_id: int,
):
    """Delete a warehouse (soft delete)."""
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id,
        Warehouse.is_deleted == False,
    ).first()

    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    name = warehouse.warehouse_name
    warehouse.is_deleted = True
    from datetime import datetime
    warehouse.deleted_at = datetime.utcnow()
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, f"Warehouse '{name}' deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Warehouse '{name}' deleted.", "success")
    return RedirectResponse(url="/inventory", status_code=303)


@router.get("/{warehouse_id}/row", response_class=HTMLResponse, dependencies=[RequireInventoryRead])
async def warehouse_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    warehouse_id: int,
):
    """Single warehouse row partial for HTMX updates."""
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id,
        Warehouse.is_deleted == False,
    ).first()

    if not warehouse:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["warehouse"] = warehouse

    template = templates.get_template("modules/inventory/templates/partials/warehouse_row.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# STOCK ENTRIES ROUTES
# =============================================================================

@router.get("/stock-entries", response_class=HTMLResponse, dependencies=[RequireInventoryRead])
async def stock_entries_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("posting_date"),
    dir: str = Query("desc"),
):
    """Stock entries list page."""
    query = db.query(StockEntry).filter(StockEntry.is_deleted == False)

    # Search
    if q:
        search_filter = or_(
            StockEntry.from_warehouse.ilike(f"%{q}%"),
            StockEntry.to_warehouse.ilike(f"%{q}%"),
            StockEntry.erpnext_id.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if type:
        query = query.filter(StockEntry.stock_entry_type == type)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(StockEntry, sort, StockEntry.posting_date)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    entries = query.offset(offset).limit(per_page).all()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["entries"] = entries
    context["search_query"] = q or ""
    context["current_type"] = type
    context["type_options"] = get_stock_entry_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/inventory/templates/partials/stock_entries_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Stock Entries"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Inventory", "href": "/inventory"},
        {"label": "Stock Entries"},
    ])

    template = templates.get_template("modules/inventory/templates/pages/stock_entries.html")
    return HTMLResponse(template.render(context))


@router.get("/stock-entries/table", response_class=HTMLResponse, dependencies=[RequireInventoryRead])
async def stock_entries_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("posting_date"),
    dir: str = Query("desc"),
):
    """Stock entries table partial for HTMX updates."""
    return await stock_entries_list(
        request, response, user, csrf_token, db,
        q, type, page, per_page, sort, dir
    )


def get_warehouse_options(db):
    """Get warehouse options for select dropdown."""
    warehouses = db.query(Warehouse).filter(
        Warehouse.is_deleted == False,
        Warehouse.is_group == False,
    ).order_by(Warehouse.warehouse_name).all()
    return [{"value": w.warehouse_name, "label": w.warehouse_name} for w in warehouses]


@router.get("/stock-entries/new", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def stock_entry_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New stock entry form page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Stock Entry"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Inventory", "href": "/inventory"},
        {"label": "Stock Entries", "href": "/inventory/stock-entries"},
        {"label": "New Entry"},
    ])
    context["entry"] = None
    context["type_options"] = get_stock_entry_type_options()
    context["warehouse_options"] = get_warehouse_options(db)
    context["errors"] = {}

    template = templates.get_template("modules/inventory/templates/pages/stock_entry_form.html")
    return HTMLResponse(template.render(context))


@router.post("/stock-entries", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def stock_entry_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new stock entry."""
    from datetime import datetime
    from decimal import Decimal

    form = await request.form()

    # Basic validation
    errors = {}
    stock_entry_type = _form_str(form, "stock_entry_type")
    posting_date = _form_str(form, "posting_date")

    if not stock_entry_type:
        errors["stock_entry_type"] = "Entry type is required"
    if not posting_date:
        errors["posting_date"] = "Posting date is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Stock Entry"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Inventory", "href": "/inventory"},
            {"label": "Stock Entries", "href": "/inventory/stock-entries"},
            {"label": "New Entry"},
        ])
        context["entry"] = None
        context["type_options"] = get_stock_entry_type_options()
        context["warehouse_options"] = get_warehouse_options(db)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/inventory/templates/pages/stock_entry_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Parse posting date
    try:
        parsed_date = datetime.strptime(posting_date, "%Y-%m-%d")
    except ValueError:
        parsed_date = datetime.utcnow()

    # Create entry
    entry = StockEntry(
        stock_entry_type=stock_entry_type,
        posting_date=parsed_date,
        posting_time=datetime.utcnow().time(),
        from_warehouse=_form_str(form, "from_warehouse") or None,
        to_warehouse=_form_str(form, "to_warehouse") or None,
        purpose=_form_str(form, "purpose") or None,
        remarks=_form_str(form, "remarks") or None,
        origin_system="local",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    set_flash(response, "Stock entry created successfully.", "success")
    return RedirectResponse(url=f"/inventory/stock-entries/{entry.id}", status_code=303)


@router.get("/stock-entries/{entry_id}", response_class=HTMLResponse, dependencies=[RequireInventoryRead])
async def stock_entry_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    entry_id: int,
):
    """Stock entry detail page."""
    entry = db.query(StockEntry).filter(
        StockEntry.id == entry_id,
        StockEntry.is_deleted == False,
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Stock entry not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Stock Entry - {entry.stock_entry_type.replace('_', ' ').title() if entry.stock_entry_type else 'Entry'}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Inventory", "href": "/inventory"},
        {"label": "Stock Entries", "href": "/inventory/stock-entries"},
        {"label": f"#{entry.id}"},
    ])
    context["entry"] = entry

    template = templates.get_template("modules/inventory/templates/pages/stock_entry_detail.html")
    return HTMLResponse(template.render(context))


@router.get("/stock-entries/{entry_id}/edit", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def stock_entry_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    entry_id: int,
):
    """Stock entry edit form page."""
    entry = db.query(StockEntry).filter(
        StockEntry.id == entry_id,
        StockEntry.is_deleted == False,
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Stock entry not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit Stock Entry"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Inventory", "href": "/inventory"},
        {"label": "Stock Entries", "href": "/inventory/stock-entries"},
        {"label": f"#{entry.id}", "href": f"/inventory/stock-entries/{entry.id}"},
        {"label": "Edit"},
    ])
    context["entry"] = entry
    context["type_options"] = get_stock_entry_type_options()
    context["warehouse_options"] = get_warehouse_options(db)
    context["errors"] = {}

    template = templates.get_template("modules/inventory/templates/pages/stock_entry_form.html")
    return HTMLResponse(template.render(context))


@router.post("/stock-entries/{entry_id}", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def stock_entry_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    entry_id: int,
):
    """Update a stock entry."""
    from datetime import datetime

    entry = db.query(StockEntry).filter(
        StockEntry.id == entry_id,
        StockEntry.is_deleted == False,
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Stock entry not found")

    form = await request.form()

    # Basic validation
    errors = {}
    stock_entry_type = _form_str(form, "stock_entry_type")
    posting_date = _form_str(form, "posting_date")

    if not stock_entry_type:
        errors["stock_entry_type"] = "Entry type is required"
    if not posting_date:
        errors["posting_date"] = "Posting date is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit Stock Entry"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Inventory", "href": "/inventory"},
            {"label": "Stock Entries", "href": "/inventory/stock-entries"},
            {"label": f"#{entry.id}", "href": f"/inventory/stock-entries/{entry.id}"},
            {"label": "Edit"},
        ])
        context["entry"] = entry
        context["type_options"] = get_stock_entry_type_options()
        context["warehouse_options"] = get_warehouse_options(db)
        context["errors"] = errors

        template = templates.get_template("modules/inventory/templates/pages/stock_entry_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Parse posting date
    try:
        parsed_date = datetime.strptime(posting_date, "%Y-%m-%d")
    except ValueError:
        parsed_date = entry.posting_date or datetime.utcnow()

    # Update entry
    entry.stock_entry_type = stock_entry_type
    entry.posting_date = parsed_date
    entry.from_warehouse = _form_str(form, "from_warehouse") or None
    entry.to_warehouse = _form_str(form, "to_warehouse") or None
    entry.purpose = _form_str(form, "purpose") or None
    entry.remarks = _form_str(form, "remarks") or None
    db.commit()

    set_flash(response, "Stock entry updated successfully.", "success")
    return RedirectResponse(url=f"/inventory/stock-entries/{entry.id}", status_code=303)


@router.delete("/stock-entries/{entry_id}", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def stock_entry_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    entry_id: int,
):
    """Delete a stock entry (soft delete)."""
    entry = db.query(StockEntry).filter(
        StockEntry.id == entry_id,
        StockEntry.is_deleted == False,
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Stock entry not found")

    entry.is_deleted = True
    from datetime import datetime
    entry.deleted_at = datetime.utcnow()
    db.commit()

    if is_htmx_request(request):
        htmx_toast(response, "Stock entry deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Stock entry deleted.", "success")
    return RedirectResponse(url="/inventory/stock-entries", status_code=303)
