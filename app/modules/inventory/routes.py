"""
Inventory Routes - Warehouse and Stock Management with SSR + HTMX.

All business logic is delegated to services. Routes are thin wrappers that:
- Parse and validate input
- Call service methods
- Map service exceptions to HTTP responses
- Control transaction boundaries (commit/rollback)

Permission Requirements:
- inventory:read - View warehouses and stock entries
- inventory:write - Create, update, delete inventory items
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, NoReturn

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import Principal, get_current_principal
from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.inventory import StockEntryType
from app.core.security import is_htmx_request, htmx_toast, set_flash
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.types import PaginationParams
from app.services.inventory import (
    WarehouseService,
    StockEntryService,
    WarehouseFilters,
    WarehouseCreateData,
    WarehouseUpdateData,
    StockEntryFilters,
    StockEntryCreateData,
    StockEntryUpdateData,
)

# Permission dependencies
RequireInventoryRead = Depends(require_scope("inventory:read"))
RequireInventoryWrite = Depends(require_scope("inventory:write"))

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = get_template_env()


# =============================================================================
# SERVICE DEPENDENCIES
# =============================================================================

def get_warehouse_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> WarehouseService:
    """Get warehouse service instance."""
    return WarehouseService(db, principal)


def get_stock_entry_service(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> StockEntryService:
    """Get stock entry service instance."""
    return StockEntryService(db, principal)


# =============================================================================
# HELPERS
# =============================================================================

def _form_str(form: Any, key: str, default: str = "") -> str:
    """Extract string value from form data."""
    value = form.get(key, default)
    if isinstance(value, UploadFile):
        return default
    if value is None:
        return default
    return str(value).strip()


def _handle_service_error(e: Exception) -> NoReturn:
    """Convert service exceptions to HTTP exceptions."""
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ValidationError):
        raise HTTPException(status_code=422, detail=str(e))
    if isinstance(e, ConflictError):
        raise HTTPException(status_code=409, detail=str(e))
    raise HTTPException(status_code=500, detail=str(e))


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
    service: WarehouseService = Depends(get_warehouse_service),
    q: Optional[str] = Query(None, description="Search query"),
    type: Optional[str] = Query(None, description="Filter by warehouse type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("warehouse_name", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Warehouse list page."""
    # Build filters and pagination
    filters = WarehouseFilters(
        search=q,
        warehouse_type=type,
        sort_by=sort,
        sort_dir=dir,
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    # Get warehouses from service
    result = service.list_warehouses(filters, pagination)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["warehouses"] = result.items
    context["search_query"] = q or ""
    context["current_type"] = type
    context["type_options"] = get_warehouse_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, result.total)

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
    service: WarehouseService = Depends(get_warehouse_service),
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("warehouse_name"),
    dir: str = Query("asc"),
):
    """Warehouse table partial for HTMX updates."""
    return await warehouses_list(
        request, response, user, csrf_token, db, service,
        q, type, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def warehouse_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    service: WarehouseService = Depends(get_warehouse_service),
):
    """New warehouse form page."""
    # Get parent warehouse options from service
    parent_warehouses = service.get_parent_warehouses()

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
    service: WarehouseService = Depends(get_warehouse_service),
):
    """Create a new warehouse."""
    form = await request.form()

    # Extract form data
    warehouse_name = _form_str(form, "warehouse_name")

    # Basic client-side validation for UX
    if not warehouse_name:
        parent_warehouses = service.get_parent_warehouses()
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
        context["errors"] = {"warehouse_name": "Warehouse name is required"}
        context["form_data"] = dict(form)

        template = templates.get_template("modules/inventory/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    try:
        # Create warehouse via service
        data = WarehouseCreateData(
            warehouse_name=warehouse_name,
            warehouse_type=_form_str(form, "warehouse_type") or None,
            parent_warehouse=_form_str(form, "parent_warehouse") or None,
            is_group=form.get("is_group") == "on",
            company=_form_str(form, "company") or None,
        )
        warehouse = service.create_warehouse(data)
        db.commit()

        set_flash(response, f"Warehouse '{warehouse.warehouse_name}' created successfully.", "success")
        return RedirectResponse(url=f"/inventory/{warehouse.id}", status_code=303)

    except (ValidationError, ConflictError) as e:
        db.rollback()
        parent_warehouses = service.get_parent_warehouses()
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
        context["errors"] = {"warehouse_name": str(e)}
        context["form_data"] = dict(form)

        template = templates.get_template("modules/inventory/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)


@router.get("/{warehouse_id}", response_class=HTMLResponse, dependencies=[RequireInventoryRead])
async def warehouse_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    warehouse_id: int,
    service: WarehouseService = Depends(get_warehouse_service),
):
    """Warehouse detail page."""
    try:
        warehouse = service.get_warehouse(warehouse_id)
    except NotFoundError:
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
    service: WarehouseService = Depends(get_warehouse_service),
):
    """Warehouse edit form page."""
    try:
        warehouse = service.get_warehouse(warehouse_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    # Get parent warehouses excluding current
    parent_warehouses = service.get_parent_warehouses_excluding(warehouse_id)

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
    service: WarehouseService = Depends(get_warehouse_service),
):
    """Update a warehouse."""
    try:
        warehouse = service.get_warehouse(warehouse_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    form = await request.form()
    warehouse_name = _form_str(form, "warehouse_name")

    # Basic client-side validation for UX
    if not warehouse_name:
        parent_warehouses = service.get_parent_warehouses_excluding(warehouse_id)
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
        context["errors"] = {"warehouse_name": "Warehouse name is required"}

        template = templates.get_template("modules/inventory/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    try:
        # Update warehouse via service
        data = WarehouseUpdateData(
            warehouse_name=warehouse_name,
            warehouse_type=_form_str(form, "warehouse_type") or None,
            parent_warehouse=_form_str(form, "parent_warehouse") or None,
            is_group=form.get("is_group") == "on",
            company=_form_str(form, "company") or None,
        )
        warehouse = service.update_warehouse(warehouse_id, data)
        db.commit()

        set_flash(response, f"Warehouse '{warehouse.warehouse_name}' updated successfully.", "success")
        return RedirectResponse(url=f"/inventory/{warehouse.id}", status_code=303)

    except (ValidationError, ConflictError) as e:
        db.rollback()
        parent_warehouses = service.get_parent_warehouses_excluding(warehouse_id)
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
        context["errors"] = {"warehouse_name": str(e)}

        template = templates.get_template("modules/inventory/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)


@router.delete("/{warehouse_id}", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def warehouse_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    warehouse_id: int,
    service: WarehouseService = Depends(get_warehouse_service),
):
    """Delete a warehouse (soft delete)."""
    try:
        warehouse = service.get_warehouse(warehouse_id)
        name = warehouse.warehouse_name
        service.delete_warehouse(warehouse_id)
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    except ValidationError as e:
        if is_htmx_request(request):
            htmx_toast(response, str(e), "error")
            return HTMLResponse("", status_code=422, headers=dict(response.headers))
        raise HTTPException(status_code=422, detail=str(e))

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
    service: WarehouseService = Depends(get_warehouse_service),
):
    """Single warehouse row partial for HTMX updates."""
    try:
        warehouse = service.get_warehouse(warehouse_id)
    except NotFoundError:
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
    service: StockEntryService = Depends(get_stock_entry_service),
    warehouse_service: WarehouseService = Depends(get_warehouse_service),
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("posting_date"),
    dir: str = Query("desc"),
):
    """Stock entries list page."""
    # Build filters and pagination
    filters = StockEntryFilters(
        search=q,
        stock_entry_type=type,
        sort_by=sort,
        sort_dir=dir,
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    # Get entries from service
    result = service.list_entries(filters, pagination)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["entries"] = result.items
    context["search_query"] = q or ""
    context["current_type"] = type
    context["type_options"] = get_stock_entry_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, result.total)

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
    service: StockEntryService = Depends(get_stock_entry_service),
    warehouse_service: WarehouseService = Depends(get_warehouse_service),
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("posting_date"),
    dir: str = Query("desc"),
):
    """Stock entries table partial for HTMX updates."""
    return await stock_entries_list(
        request, response, user, csrf_token, db, service, warehouse_service,
        q, type, page, per_page, sort, dir
    )


def _get_warehouse_options(service: WarehouseService):
    """Get warehouse options for select dropdown using service."""
    warehouses = service.get_leaf_warehouses()
    return [{"value": w.warehouse_name, "label": w.warehouse_name} for w in warehouses]


@router.get("/stock-entries/new", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def stock_entry_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    warehouse_service: WarehouseService = Depends(get_warehouse_service),
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
    context["warehouse_options"] = _get_warehouse_options(warehouse_service)
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
    service: StockEntryService = Depends(get_stock_entry_service),
    warehouse_service: WarehouseService = Depends(get_warehouse_service),
):
    """Create a new stock entry."""
    form = await request.form()

    # Extract and validate form data
    stock_entry_type = _form_str(form, "stock_entry_type")
    posting_date_str = _form_str(form, "posting_date")

    errors = {}
    if not stock_entry_type:
        errors["stock_entry_type"] = "Entry type is required"
    if not posting_date_str:
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
        context["warehouse_options"] = _get_warehouse_options(warehouse_service)
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/inventory/templates/pages/stock_entry_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Parse posting date
    from datetime import date as date_type
    try:
        parsed_date = datetime.strptime(posting_date_str, "%Y-%m-%d").date()
    except ValueError:
        parsed_date = date_type.today()

    try:
        # Create entry via service
        data = StockEntryCreateData(
            stock_entry_type=stock_entry_type,
            posting_date=parsed_date,
            posting_time=datetime.utcnow().strftime("%H:%M:%S"),
            from_warehouse=_form_str(form, "from_warehouse") or None,
            to_warehouse=_form_str(form, "to_warehouse") or None,
            purpose=_form_str(form, "purpose") or None,
            remarks=_form_str(form, "remarks") or None,
        )
        entry = service.create_entry(data)
        db.commit()

        set_flash(response, "Stock entry created successfully.", "success")
        return RedirectResponse(url=f"/inventory/stock-entries/{entry.id}", status_code=303)

    except ValidationError as e:
        db.rollback()
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
        context["warehouse_options"] = _get_warehouse_options(warehouse_service)
        context["errors"] = {"general": str(e)}
        context["form_data"] = dict(form)

        template = templates.get_template("modules/inventory/templates/pages/stock_entry_form.html")
        return HTMLResponse(template.render(context), status_code=422)


@router.get("/stock-entries/{entry_id}", response_class=HTMLResponse, dependencies=[RequireInventoryRead])
async def stock_entry_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    entry_id: int,
    service: StockEntryService = Depends(get_stock_entry_service),
):
    """Stock entry detail page."""
    try:
        entry = service.get_entry(entry_id, include_items=True)
    except NotFoundError:
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
    service: StockEntryService = Depends(get_stock_entry_service),
    warehouse_service: WarehouseService = Depends(get_warehouse_service),
):
    """Stock entry edit form page."""
    try:
        entry = service.get_entry(entry_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Stock entry not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Edit Stock Entry"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Operations"},
        {"label": "Inventory", "href": "/inventory"},
        {"label": "Stock Entries", "href": "/inventory/stock-entries"},
        {"label": f"#{entry.id}", "href": f"/inventory/stock-entries/{entry.id}"},
        {"label": "Edit"},
    ])
    context["entry"] = entry
    context["type_options"] = get_stock_entry_type_options()
    context["warehouse_options"] = _get_warehouse_options(warehouse_service)
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
    service: StockEntryService = Depends(get_stock_entry_service),
    warehouse_service: WarehouseService = Depends(get_warehouse_service),
):
    """Update a stock entry."""
    try:
        entry = service.get_entry(entry_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Stock entry not found")

    form = await request.form()

    # Extract and validate form data
    stock_entry_type = _form_str(form, "stock_entry_type")
    posting_date_str = _form_str(form, "posting_date")

    errors = {}
    if not stock_entry_type:
        errors["stock_entry_type"] = "Entry type is required"
    if not posting_date_str:
        errors["posting_date"] = "Posting date is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Stock Entry"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Inventory", "href": "/inventory"},
            {"label": "Stock Entries", "href": "/inventory/stock-entries"},
            {"label": f"#{entry.id}", "href": f"/inventory/stock-entries/{entry.id}"},
            {"label": "Edit"},
        ])
        context["entry"] = entry
        context["type_options"] = get_stock_entry_type_options()
        context["warehouse_options"] = _get_warehouse_options(warehouse_service)
        context["errors"] = errors

        template = templates.get_template("modules/inventory/templates/pages/stock_entry_form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Parse posting date
    from datetime import date as date_type
    try:
        parsed_date = datetime.strptime(posting_date_str, "%Y-%m-%d").date()
    except ValueError:
        parsed_date = entry.posting_date.date() if entry.posting_date else date_type.today()

    try:
        # Update entry via service
        data = StockEntryUpdateData(
            stock_entry_type=stock_entry_type,
            posting_date=parsed_date,
            from_warehouse=_form_str(form, "from_warehouse") or None,
            to_warehouse=_form_str(form, "to_warehouse") or None,
            purpose=_form_str(form, "purpose") or None,
            remarks=_form_str(form, "remarks") or None,
        )
        entry = service.update_entry(entry_id, data)
        db.commit()

        set_flash(response, "Stock entry updated successfully.", "success")
        return RedirectResponse(url=f"/inventory/stock-entries/{entry.id}", status_code=303)

    except ValidationError as e:
        db.rollback()
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Stock Entry"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Operations"},
            {"label": "Inventory", "href": "/inventory"},
            {"label": "Stock Entries", "href": "/inventory/stock-entries"},
            {"label": f"#{entry.id}", "href": f"/inventory/stock-entries/{entry.id}"},
            {"label": "Edit"},
        ])
        context["entry"] = entry
        context["type_options"] = get_stock_entry_type_options()
        context["warehouse_options"] = _get_warehouse_options(warehouse_service)
        context["errors"] = {"general": str(e)}

        template = templates.get_template("modules/inventory/templates/pages/stock_entry_form.html")
        return HTMLResponse(template.render(context), status_code=422)


@router.delete("/stock-entries/{entry_id}", response_class=HTMLResponse, dependencies=[RequireInventoryWrite])
async def stock_entry_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    entry_id: int,
    service: StockEntryService = Depends(get_stock_entry_service),
):
    """Delete a stock entry (soft delete)."""
    try:
        service.delete_entry(entry_id)
        db.commit()
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Stock entry not found")
    except ValidationError as e:
        if is_htmx_request(request):
            htmx_toast(response, str(e), "error")
            return HTMLResponse("", status_code=422, headers=dict(response.headers))
        raise HTTPException(status_code=422, detail=str(e))

    if is_htmx_request(request):
        htmx_toast(response, "Stock entry deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, "Stock entry deleted.", "success")
    return RedirectResponse(url="/inventory/stock-entries", status_code=303)
