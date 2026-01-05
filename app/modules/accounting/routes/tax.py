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
from decimal import Decimal

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException, set_flash, validate_csrf, form_str, form_decimal, form_int,
)
from app.services.accounting import TaxService
from app.services.accounting.web_services import AccountingTaxWebService
from app.services.accounting.tax_types import (
    TaxCodeCreateData,
    TaxCodeFilters,
    TaxCodeUpdateData,
    TaxFilingCreateData,
    TaxFilingFilters,
    TaxPaymentCreateData,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams
from app.models.tax import TaxFilingType, TaxType, RoundingMethod

router = APIRouter()


def _get_tax_service(db: DB, user: SessionUser) -> TaxService:
    return TaxService(db, user)


def _get_tax_web_service(db: DB, user: SessionUser) -> AccountingTaxWebService:
    return AccountingTaxWebService(db, _get_tax_service(db, user))


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _tax_type_options() -> list:
    return [
        {"value": TaxType.SALES.value, "label": "Sales"},
        {"value": TaxType.PURCHASE.value, "label": "Purchase"},
        {"value": TaxType.BOTH.value, "label": "Both"},
    ]


def _rounding_method_options() -> list:
    return [
        {"value": RoundingMethod.ROUND.value, "label": "Round"},
        {"value": RoundingMethod.FLOOR.value, "label": "Floor"},
        {"value": RoundingMethod.CEIL.value, "label": "Ceil"},
    ]


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
    web_service = _get_tax_web_service(db, user)
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


@router.get("/tax-codes/new", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def tax_code_form_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New tax code form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Tax Codes", "href": "/accounting/tax-codes"},
        {"label": "New", "href": None},
    ])
    context["page_title"] = "New Tax Code"
    context["tax_code"] = None
    context["tax_type_options"] = _tax_type_options()
    context["rounding_method_options"] = _rounding_method_options()
    context["is_edit"] = False

    template = templates.get_template("modules/accounting/templates/tax/pages/code_form.html")
    return HTMLResponse(template.render(context))


@router.get("/tax-codes/{tc_id}/edit", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def tax_code_form_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    tc_id: int,
):
    """Edit tax code form."""
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
        {"label": tax_code.code, "href": f"/accounting/tax-codes/{tc_id}"},
        {"label": "Edit", "href": None},
    ])
    context["page_title"] = f"Edit: {tax_code.code}"
    context["tax_code"] = tax_code
    context["tax_type_options"] = _tax_type_options()
    context["rounding_method_options"] = _rounding_method_options()
    context["is_edit"] = True

    template = templates.get_template("modules/accounting/templates/tax/pages/code_form.html")
    return HTMLResponse(template.render(context))


@router.post("/tax-codes", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def tax_code_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf_protect: CSRFProtect,
    db: DB,
):
    """Create a tax code."""
    await validate_csrf(request, csrf_protect)

    form = await request.form()
    web_service = _get_tax_web_service(db, user)

    code = form_str(form, "code")
    name = form_str(form, "name")
    description = form_str(form, "description") or None
    rate = form_decimal(form, "rate", default=Decimal("0")) or Decimal("0")
    tax_type = form_str(form, "tax_type") or TaxType.BOTH.value
    rounding_method = form_str(form, "rounding_method") or RoundingMethod.ROUND.value
    rounding_precision = form_int(form, "rounding_precision", default=2) or 2
    is_tax_inclusive = form_str(form, "is_tax_inclusive") == "on"
    is_active = form_str(form, "is_active") == "on"
    jurisdiction = form_str(form, "jurisdiction") or None
    country = form_str(form, "country") or None
    account_head = form_str(form, "account_head") or None
    cost_center = form_str(form, "cost_center") or None
    company = form_str(form, "company") or None
    valid_from = _parse_date(form_str(form, "valid_from"))
    valid_to = _parse_date(form_str(form, "valid_to"))

    try:
        create_data = TaxCodeCreateData(
            code=code,
            name=name,
            description=description,
            rate=rate,
            tax_type=tax_type,
            is_tax_inclusive=is_tax_inclusive,
            rounding_method=rounding_method,
            rounding_precision=rounding_precision,
            jurisdiction=jurisdiction,
            country=country,
            account_head=account_head,
            cost_center=cost_center,
            valid_from=valid_from,
            valid_to=valid_to,
            company=company,
        )
        tax_code = web_service.create_tax_code(create_data, user_id=user.id)
        if not is_active:
            web_service.update_tax_code(
                tax_code.id,
                TaxCodeUpdateData(is_active=False),
            )
        set_flash(response, "Tax code created successfully", "success")
        return RedirectResponse(
            url=f"/accounting/tax-codes/{tax_code.id}",
            status_code=303,
        )
    except ValidationError as exc:
        web_service.rollback()
        set_flash(response, str(exc), "error")
        return RedirectResponse(url="/accounting/tax-codes/new", status_code=303)


@router.post("/tax-codes/{tc_id}", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def tax_code_update(
    tc_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf_protect: CSRFProtect,
    db: DB,
):
    """Update a tax code."""
    await validate_csrf(request, csrf_protect)

    form = await request.form()
    web_service = _get_tax_web_service(db, user)

    name = form_str(form, "name") or None
    description = form_str(form, "description") or None
    rate = form_decimal(form, "rate", default=None)
    tax_type = form_str(form, "tax_type") or None
    rounding_method = form_str(form, "rounding_method") or None
    rounding_precision = form_int(form, "rounding_precision", default=None)
    is_tax_inclusive = form_str(form, "is_tax_inclusive") == "on"
    is_active = form_str(form, "is_active") == "on"
    jurisdiction = form_str(form, "jurisdiction") or None
    country = form_str(form, "country") or None
    account_head = form_str(form, "account_head") or None
    cost_center = form_str(form, "cost_center") or None
    company = form_str(form, "company") or None
    valid_from = _parse_date(form_str(form, "valid_from"))
    valid_to = _parse_date(form_str(form, "valid_to"))

    update_data = TaxCodeUpdateData(
        name=name,
        description=description,
        rate=rate,
        tax_type=tax_type,
        is_tax_inclusive=is_tax_inclusive,
        rounding_method=rounding_method,
        rounding_precision=rounding_precision,
        jurisdiction=jurisdiction,
        country=country,
        account_head=account_head,
        cost_center=cost_center,
        valid_from=valid_from,
        valid_to=valid_to,
        company=company,
        is_active=is_active,
    )

    try:
        web_service.update_tax_code(tc_id, update_data)
        set_flash(response, "Tax code updated successfully", "success")
        return RedirectResponse(
            url=f"/accounting/tax-codes/{tc_id}",
            status_code=303,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        web_service.rollback()
        set_flash(response, str(exc), "error")
        return RedirectResponse(
            url=f"/accounting/tax-codes/{tc_id}/edit",
            status_code=303,
        )


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
        period = web_service.create_filing_period(
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
    web_service = _get_tax_web_service(db, user)
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
        web_service.record_payment(
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
    web_service = _get_tax_web_service(db, user)
    try:
        period = web_service.file_period(period_id, user_id=user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        set_flash(response, str(exc), "warning")
        return RedirectResponse(url=f"/accounting/tax/filing/{period_id}", status_code=303)

    set_flash(response, "Tax period marked as filed", "success")

    if is_htmx_request(request):
        return RedirectResponse(url="/accounting/tax/filing", status_code=303)
    return RedirectResponse(url=f"/accounting/tax/filing/{period_id}", status_code=303)
