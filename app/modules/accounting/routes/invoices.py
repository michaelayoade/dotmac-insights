"""
Invoice routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException,
    validate_csrf, set_flash, form_str, form_int, form_decimal,
    datetime, Decimal,
    InvoiceStatus,
)
from app.services.accounting import AccountingSettingsService, InvoiceService, ReceivablesService
from app.services.accounting.invoice_types import InvoiceFilters, InvoiceCreateData, InvoiceLineData
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams
from app.utils.company_context import get_company_context

router = APIRouter()


def get_invoice_status_options():
    """Get status options for invoice filter dropdown."""
    options = [
        {"value": "unpaid", "label": "Unpaid"},
        *[
            {"value": s.value, "label": s.value.replace("_", " ").title()}
            for s in InvoiceStatus
        ],
    ]
    return options


def _get_invoice_service(db: DB, user: SessionUser) -> InvoiceService:
    return InvoiceService(db, user)


def _get_receivables_service(db: DB, user: SessionUser) -> ReceivablesService:
    settings_service = AccountingSettingsService(db, user)
    return ReceivablesService(db, settings_service, user)


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _get_customer_options(service: ReceivablesService) -> list[dict[str, str]]:
    customers = service.list_customer_accounts()
    return [
        {
            "value": str(customer.id),
            "label": customer.party.name if customer.party else f"Customer {customer.id}",
        }
        for customer in customers
    ]


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
    status_in = None
    if status:
        if status == "unpaid":
            status_in = [
                InvoiceStatus.DRAFT,
                InvoiceStatus.PENDING,
                InvoiceStatus.PARTIALLY_PAID,
                InvoiceStatus.OVERDUE,
            ]
        else:
            try:
                status_enum = InvoiceStatus(status)
            except ValueError:
                status_enum = None

    filters = InvoiceFilters(
        search=q,
        status=status_enum,
        status_in=status_in,
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


@router.get("/invoices/{invoice_id:int}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
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


@router.get("/invoices/new", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def invoice_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Invoice creation form."""
    receivables_service = _get_receivables_service(db, user)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Invoice"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Finance", "href": "/accounting/invoices"},
        {"label": "Invoices", "href": "/accounting/invoices"},
        {"label": "New"},
    ])
    context["customer_options"] = _get_customer_options(receivables_service)
    context["errors"] = {}
    context["form_data"] = {}

    template = templates.get_template("modules/accounting/templates/invoices/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/invoices", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def invoice_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Create a new invoice."""
    await validate_csrf(request)

    form = await request.form()
    customer_id = form_int(form, "customer_id")
    invoice_date = _parse_date(form_str(form, "invoice_date"))
    due_date = _parse_date(form_str(form, "due_date"))
    description = form_str(form, "description") or None

    errors: dict[str, str] = {}
    if not customer_id:
        errors["customer_id"] = "Customer is required"
    if not invoice_date:
        errors["invoice_date"] = "Invoice date is required"

    line_indices = []
    for key in form.keys():
        if key.startswith("line_description_"):
            try:
                line_indices.append(int(key.rsplit("_", 1)[-1]))
            except ValueError:
                continue
    line_indices = sorted(set(line_indices))

    lines: list[InvoiceLineData] = []
    for idx in line_indices:
        description_value = form_str(form, f"line_description_{idx}")
        quantity_value = form_decimal(form, f"line_quantity_{idx}", Decimal("1")) or Decimal("1")
        unit_price_value = form_decimal(form, f"line_unit_price_{idx}", Decimal("0")) or Decimal("0")

        if not description_value and unit_price_value == Decimal("0"):
            continue
        if not description_value:
            errors["lines"] = "Each line item requires a description"
            continue

        amount_value = quantity_value * unit_price_value
        lines.append(InvoiceLineData(
            description=description_value,
            quantity=quantity_value,
            rate=unit_price_value,
            amount=amount_value,
        ))

    if not lines:
        errors["lines"] = errors.get("lines") or "At least one line item is required"

    if errors:
        receivables_service = _get_receivables_service(db, user)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Invoice"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Finance", "href": "/accounting/invoices"},
            {"label": "Invoices", "href": "/accounting/invoices"},
            {"label": "New"},
        ])
        context["customer_options"] = _get_customer_options(receivables_service)
        context["errors"] = errors
        context["form_data"] = {
            "customer_id": str(customer_id) if customer_id else "",
            "invoice_date": form_str(form, "invoice_date"),
            "due_date": form_str(form, "due_date"),
            "description": description or "",
        }

        template = templates.get_template("modules/accounting/templates/invoices/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service = _get_invoice_service(db, user)
    company = get_company_context(allow_null=True)
    try:
        invoice = service.create_invoice(InvoiceCreateData(
            customer_account_id=customer_id,
            invoice_date=invoice_date,
            due_date=due_date,
            description=description,
            lines=lines,
            company=company,
        ))
        db.commit()
    except ValidationError as exc:
        db.rollback()
        receivables_service = _get_receivables_service(db, user)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Invoice"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Finance", "href": "/accounting/invoices"},
            {"label": "Invoices", "href": "/accounting/invoices"},
            {"label": "New"},
        ])
        context["customer_options"] = _get_customer_options(receivables_service)
        context["errors"] = {"form": str(exc)}
        context["form_data"] = {
            "customer_id": str(customer_id) if customer_id else "",
            "invoice_date": form_str(form, "invoice_date"),
            "due_date": form_str(form, "due_date"),
            "description": description or "",
        }
        template = templates.get_template("modules/accounting/templates/invoices/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    redirect = RedirectResponse(url=f"/accounting/invoices/{invoice.id}", status_code=303)
    set_flash(redirect, "Invoice created successfully.", "success")
    return redirect
