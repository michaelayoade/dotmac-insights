"""
Invoice routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException,
    InvoiceStatus,
)
from app.services.accounting import AccountingSettingsService, InvoiceService, ReceivablesService
from app.services.accounting.invoice_types import InvoiceFilters
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter()


def get_invoice_status_options():
    """Get status options for invoice filter dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in InvoiceStatus
    ]


def _get_invoice_service(db: DB, user: SessionUser) -> InvoiceService:
    return InvoiceService(db, user)


def _get_receivables_service(db: DB, user: SessionUser) -> ReceivablesService:
    settings_service = AccountingSettingsService(db, user)
    return ReceivablesService(db, settings_service, user)


@router.get("/invoices", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def invoices_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("invoice_date", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Invoices list page."""
    service = _get_invoice_service(db, user)
    status_enum = None
    if status:
        try:
            status_enum = InvoiceStatus(status)
        except ValueError:
            status_enum = None

    filters = InvoiceFilters(
        search=q,
        status=status_enum,
        sort_by=sort,
        sort_dir=dir,
    )
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_invoices(filters, pagination)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    invoices = result.items
    total = result.total

    stats_service = _get_receivables_service(db, user)
    stats = stats_service.get_invoice_list_stats()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["invoices"] = invoices
    context["search_query"] = q or ""
    context["current_status"] = status
    context["status_options"] = get_invoice_status_options()
    context["stats"] = stats
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/invoices/partials/invoices_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Invoices"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Finance", "href": "/accounting/invoices"},
        {"label": "Invoices"},
    ])

    template = templates.get_template("modules/accounting/templates/invoices/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/invoices/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def invoices_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("invoice_date"),
    dir: str = Query("desc"),
):
    """Invoices table partial for HTMX updates."""
    return await invoices_list(
        request, response, user, csrf_token, db,
        q, status, page, per_page, sort, dir
    )


@router.get("/invoices/{invoice_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def invoice_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    invoice_id: int,
):
    """Invoice detail page."""
    service = _get_invoice_service(db, user)
    try:
        invoice = service.get_invoice(invoice_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Invoice not found") from exc

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = invoice.invoice_number or f"INV-{invoice.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Finance", "href": "/accounting/invoices"},
        {"label": "Invoices", "href": "/accounting/invoices"},
        {"label": invoice.invoice_number or f"INV-{invoice.id}"},
    ])
    context["invoice"] = invoice

    template = templates.get_template("modules/accounting/templates/invoices/pages/detail.html")
    return HTMLResponse(template.render(context))
