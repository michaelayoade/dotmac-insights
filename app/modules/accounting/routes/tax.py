"""
Tax routes for accounting module.

Provides UI pages for:
- Tax codes management
- Tax filing periods
- Tax templates
- Tax dashboard
"""
from fastapi import APIRouter, Query
from datetime import date, datetime

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException, set_flash, validate_csrf, form_str, form_decimal,
)
from app.services.accounting import TaxService
from app.services.accounting.tax_types import TaxCodeFilters, TaxFilingCreateData, TaxFilingFilters, TaxPaymentCreateData
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams
from app.models.tax import TaxFilingType

router = APIRouter()


def _get_tax_service(db: DB, user: SessionUser) -> TaxService:
    return TaxService(db, user)


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


# =============================================================================
# TAX CODES
# =============================================================================


@router.get("/tax-codes", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_codes_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    tax_type: Optional[str] = Query(None),
    is_active: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Tax codes list page."""
    service = _get_tax_service(db, user)
    active_filter = None
    if is_active is not None:
        active_filter = is_active == "true"

    filters = TaxCodeFilters(query=q, tax_type=tax_type, is_active=active_filter)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    try:
        result = service.list_tax_codes(filters, pagination)
    except ValidationError as exc:
        set_flash(response, str(exc), "warning")
        filters.tax_type = None
        result = service.list_tax_codes(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Tax Codes"},
    ])
    context["tax_codes"] = result.items
    context["stats"] = service.get_tax_code_stats()
    context["current_search"] = q
    context["current_type"] = tax_type
    context["current_active"] = is_active
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/tax/partials/tax_codes_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/tax/pages/codes_list.html")

    return HTMLResponse(template.render(context))


@router.get("/tax-codes/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_codes_table_partial(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    tax_type: Optional[str] = Query(None),
    is_active: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Tax codes table HTMX partial."""
    service = _get_tax_service(db, user)
    active_filter = None
    if is_active is not None:
        active_filter = is_active == "true"

    filters = TaxCodeFilters(query=q, tax_type=tax_type, is_active=active_filter)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    try:
        result = service.list_tax_codes(filters, pagination)
    except ValidationError:
        filters.tax_type = None
        result = service.list_tax_codes(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["tax_codes"] = result.items
    context["current_search"] = q
    context["current_type"] = tax_type
    context["current_active"] = is_active
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    template = templates.get_template("modules/accounting/templates/tax/partials/tax_codes_table.html")
    return HTMLResponse(template.render(context))


@router.get("/tax-codes/{tc_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_code_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    tc_id: int,
):
    """Tax code detail page."""
    service = _get_tax_service(db, user)
    try:
        tax_code = service.get_tax_code(tc_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Tax Codes", "href": "/accounting/tax-codes"},
        {"label": tax_code.code},
    ])
    context["tax_code"] = tax_code

    template = templates.get_template("modules/accounting/templates/tax/pages/code_detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# TAX FILING PERIODS
# =============================================================================


@router.get("/tax/filing", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_filing_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    tax_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Tax filing periods list page."""
    service = _get_tax_service(db, user)
    filters = TaxFilingFilters(tax_type=tax_type, status=status, year=year)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    try:
        result = service.list_filing_periods(filters, pagination)
    except ValidationError as exc:
        set_flash(response, str(exc), "warning")
        filters.tax_type = None
        filters.status = None
        result = service.list_filing_periods(filters, pagination)

    years = service.list_filing_years()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Tax Filing"},
    ])
    context["periods"] = result.items
    context["stats"] = service.get_filing_stats()
    context["dashboard"] = service.get_dashboard_summary()
    context["years"] = years
    context["current_type"] = tax_type
    context["current_status"] = status
    context["current_year"] = year
    context["today"] = date.today()
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/tax/partials/filing_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/tax/pages/filing_list.html")

    return HTMLResponse(template.render(context))


@router.get("/tax/filing/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_filing_table_partial(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    tax_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Tax filing table HTMX partial."""
    service = _get_tax_service(db, user)
    filters = TaxFilingFilters(tax_type=tax_type, status=status, year=year)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    try:
        result = service.list_filing_periods(filters, pagination)
    except ValidationError:
        filters.tax_type = None
        filters.status = None
        result = service.list_filing_periods(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["periods"] = result.items
    context["today"] = date.today()
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    template = templates.get_template("modules/accounting/templates/tax/partials/filing_table.html")
    return HTMLResponse(template.render(context))


@router.get("/tax/filing/new", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def tax_filing_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New tax filing period form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Tax Filing", "href": "/accounting/tax/filing"},
        {"label": "New Filing Period", "href": "/accounting/tax/filing/new", "current": True},
    ])
    context["tax_type_options"] = [t.value for t in TaxFilingType]

    template = templates.get_template("modules/accounting/templates/tax/pages/filing_form.html")
    return HTMLResponse(template.render(context))


@router.post("/tax/filing/new", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def tax_filing_create(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
):
    """Create a tax filing period."""
    form_data = await request.form()
    await validate_csrf(request)

    service = _get_tax_service(db, user)
    period_start = _parse_date(form_str(form_data, "period_start"))
    period_end = _parse_date(form_str(form_data, "period_end"))
    due_date = _parse_date(form_str(form_data, "due_date"))

    if not period_start or not period_end or not due_date:
        set_flash(response, "Please provide valid period and due dates.", "warning")
        return RedirectResponse(url="/accounting/tax/filing/new", status_code=303)

    try:
        period = service.create_filing_period(
            TaxFilingCreateData(
                tax_type=form_str(form_data, "tax_type"),
                period_name=form_str(form_data, "period_name"),
                period_start=period_start,
                period_end=period_end,
                due_date=due_date,
                tax_base=form_decimal(form_data, "tax_base") or 0,
                tax_amount=form_decimal(form_data, "tax_amount") or 0,
            ),
            user_id=user.id,
        )
    except ValidationError as exc:
        set_flash(response, str(exc), "warning")
        return RedirectResponse(url="/accounting/tax/filing/new", status_code=303)

    db.commit()
    set_flash(response, "Tax filing period created", "success")
    return RedirectResponse(url=f"/accounting/tax/filing/{period.id}", status_code=303)


@router.get("/tax/filing/{period_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def tax_filing_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    period_id: int,
):
    """Tax filing period detail page."""
    service = _get_tax_service(db, user)
    try:
        period = service.get_filing_period(period_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    payments = service.get_period_payments(period_id)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Tax Filing", "href": "/accounting/tax/filing"},
        {"label": period.period_name},
    ])
    context["period"] = period
    context["today"] = date.today()
    context["payments"] = payments
    context["today"] = date.today()

    template = templates.get_template("modules/accounting/templates/tax/pages/filing_detail.html")
    return HTMLResponse(template.render(context))


@router.get("/tax/filing/{period_id}/pay", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def tax_filing_payment_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    period_id: int,
):
    """Record tax payment form."""
    service = _get_tax_service(db, user)
    try:
        period = service.get_filing_period(period_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Tax Filing", "href": "/accounting/tax/filing"},
        {"label": period.period_name, "href": f"/accounting/tax/filing/{period_id}"},
        {"label": "Record Payment", "href": f"/accounting/tax/filing/{period_id}/pay", "current": True},
    ])
    context["period"] = period

    template = templates.get_template("modules/accounting/templates/tax/pages/payment_form.html")
    return HTMLResponse(template.render(context))


@router.post("/tax/filing/{period_id}/pay", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def tax_filing_record_payment(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    period_id: int,
):
    """Record a tax payment for a filing period."""
    form_data = await request.form()
    await validate_csrf(request)

    service = _get_tax_service(db, user)
    payment_date = _parse_date(form_str(form_data, "payment_date")) or date.today()
    amount = form_decimal(form_data, "amount")

    if amount is None:
        set_flash(response, "Payment amount is required.", "warning")
        return RedirectResponse(url=f"/accounting/tax/filing/{period_id}/pay", status_code=303)

    try:
        service.record_payment(
            period_id,
            TaxPaymentCreateData(
                payment_date=payment_date,
                amount=amount,
                payment_reference=form_str(form_data, "payment_reference") or None,
                payment_method=form_str(form_data, "payment_method") or None,
                bank_account=form_str(form_data, "bank_account") or None,
            ),
            user_id=user.id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        set_flash(response, str(exc), "warning")
        return RedirectResponse(url=f"/accounting/tax/filing/{period_id}/pay", status_code=303)

    db.commit()
    set_flash(response, "Tax payment recorded", "success")
    return RedirectResponse(url=f"/accounting/tax/filing/{period_id}", status_code=303)


@router.post("/tax/filing/{period_id}/file", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def tax_filing_mark_filed(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    period_id: int,
):
    """Mark a tax filing period as filed."""
    service = _get_tax_service(db, user)
    try:
        period = service.file_period(period_id, user_id=user.id)
        db.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        set_flash(response, str(exc), "warning")
        return RedirectResponse(url=f"/accounting/tax/filing/{period_id}", status_code=303)

    set_flash(response, "Tax period marked as filed", "success")

    if is_htmx_request(request):
        return RedirectResponse(url="/accounting/tax/filing", status_code=303)
    return RedirectResponse(url=f"/accounting/tax/filing/{period_id}", status_code=303)
