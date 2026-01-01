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
    Invoice, InvoiceStatus,
    func, or_, datetime, Decimal,
)

router = APIRouter()


def get_invoice_status_options():
    """Get status options for invoice filter dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in InvoiceStatus
    ]


def get_invoice_stats(db) -> dict:
    """Calculate invoice statistics."""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Total count
    total_count = db.query(func.count(Invoice.id)).scalar() or 0

    # Outstanding (pending + partially_paid)
    outstanding = db.query(func.sum(Invoice.balance)).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID])
    ).scalar() or Decimal("0")

    # Overdue
    overdue = db.query(func.sum(Invoice.balance)).filter(
        Invoice.status == InvoiceStatus.OVERDUE
    ).scalar() or Decimal("0")

    # Paid this month
    paid_this_month = db.query(func.sum(Invoice.amount_paid)).filter(
        Invoice.paid_date >= month_start
    ).scalar() or Decimal("0")

    return {
        "total_count": total_count,
        "outstanding": outstanding,
        "overdue": overdue,
        "paid_this_month": paid_this_month,
    }


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
    # Build query
    query = db.query(Invoice)

    # Search
    if q:
        search_filter = or_(
            Invoice.invoice_number.ilike(f"%{q}%"),
            Invoice.description.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(Invoice.status == status)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(Invoice, sort, Invoice.invoice_date)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    invoices = query.offset(offset).limit(per_page).all()

    # Get stats
    stats = get_invoice_stats(db)

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
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

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
