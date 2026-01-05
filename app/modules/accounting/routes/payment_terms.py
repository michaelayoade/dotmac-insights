"""
Payment Terms routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional, Decimal,
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException, set_flash, validate_csrf, form_str, form_int, form_decimal,
)
from app.services.accounting import PaymentTermsService
from app.services.accounting.web_services import AccountingPaymentTermsWebService
from app.services.accounting.payment_terms_types import (
    PaymentTermsFilters,
    PaymentTermsCreateData,
    PaymentTermsUpdateData,
    ScheduleData,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter()


def _get_service(db: DB, user: SessionUser) -> PaymentTermsService:
    return PaymentTermsService(db, user)


def _get_web_service(db: DB, user: SessionUser) -> AccountingPaymentTermsWebService:
    return AccountingPaymentTermsWebService(db, _get_service(db, user))


@router.get("/payment-terms", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def payment_terms_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    is_active: Optional[bool] = Query(None, description="Active filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Payment terms list page."""
    service = _get_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)

    filters = PaymentTermsFilters(
        is_active=is_active,
        search=q,
    )

    result = service.list_payment_terms(filters, pagination)
    terms = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Payment Terms", "href": None},
    ])
    context["page_title"] = "Payment Terms"
    context["terms"] = terms
    context["total"] = total
    context["current_search"] = q
    context["current_active"] = is_active
    context["pagination"] = build_pagination_context(
        page=page,
        per_page=per_page,
        total=total,
    )

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/payment_terms/partials/terms_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/payment_terms/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/payment-terms/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def payment_terms_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    is_active: Optional[bool] = Query(None, description="Active filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Payment terms table partial (HTMX)."""
    service = _get_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)

    filters = PaymentTermsFilters(
        is_active=is_active,
        search=q,
    )

    result = service.list_payment_terms(filters, pagination)

    context = get_base_context(request, response, user, csrf_token)
    context["terms"] = result.items
    context["total"] = result.total
    context["current_search"] = q
    context["pagination"] = build_pagination_context(
        page=page,
        per_page=per_page,
        total=result.total,
        base_url="/accounting/payment-terms",
    )

    template = templates.get_template("modules/accounting/templates/payment_terms/partials/terms_table.html")
    return HTMLResponse(template.render(context))


@router.get("/payment-terms/new", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def payment_terms_form_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New payment terms form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Payment Terms", "href": "/accounting/payment-terms"},
        {"label": "New", "href": None},
    ])
    context["page_title"] = "New Payment Terms"
    context["terms"] = None
    context["schedules"] = []
    context["is_edit"] = False

    template = templates.get_template("modules/accounting/templates/payment_terms/pages/form.html")
    return HTMLResponse(template.render(context))


@router.get("/payment-terms/{terms_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def payment_terms_detail(
    terms_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Payment terms detail page."""
    service = _get_service(db, user)

    try:
        terms = service.get_payment_terms(terms_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment terms not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Payment Terms", "href": "/accounting/payment-terms"},
        {"label": terms.template_name, "href": None},
    ])
    context["page_title"] = f"Payment Terms: {terms.template_name}"
    context["terms"] = terms
    context["schedules"] = sorted(terms.schedules, key=lambda s: s.idx) if terms.schedules else []

    template = templates.get_template("modules/accounting/templates/payment_terms/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/payment-terms/{terms_id}/edit", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def payment_terms_form_edit(
    terms_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Edit payment terms form."""
    service = _get_service(db, user)

    try:
        terms = service.get_payment_terms(terms_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment terms not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Payment Terms", "href": "/accounting/payment-terms"},
        {"label": terms.template_name, "href": f"/accounting/payment-terms/{terms_id}"},
        {"label": "Edit", "href": None},
    ])
    context["page_title"] = f"Edit: {terms.template_name}"
    context["terms"] = terms
    context["schedules"] = sorted(terms.schedules, key=lambda s: s.idx) if terms.schedules else []
    context["is_edit"] = True

    template = templates.get_template("modules/accounting/templates/payment_terms/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/payment-terms", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def payment_terms_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf_protect: CSRFProtect,
    db: DB,
):
    """Create new payment terms."""
    await validate_csrf(request, csrf_protect)

    form = await request.form()
    service = _get_service(db, user)

    template_name = form_str(form, "template_name")
    description = form_str(form, "description") or None

    # Parse schedules from form
    schedules = []
    idx = 0
    while f"schedule_{idx}_percentage" in form:
        schedules.append(ScheduleData(
            credit_days=form_int(form, f"schedule_{idx}_credit_days", 0) or 0,
            credit_months=form_int(form, f"schedule_{idx}_credit_months", 0) or 0,
            day_of_month=form_int(form, f"schedule_{idx}_day_of_month"),
            payment_percentage=form_decimal(form, f"schedule_{idx}_percentage", Decimal("100")) or Decimal("100"),
            discount_percentage=form_decimal(form, f"schedule_{idx}_discount", Decimal("0")) or Decimal("0"),
            discount_days=form_int(form, f"schedule_{idx}_discount_days", 0) or 0,
            description=form_str(form, f"schedule_{idx}_description") or None,
        ))
        idx += 1

    try:
        create_data = PaymentTermsCreateData(
            template_name=template_name,
            description=description,
            schedules=schedules,
        )
        web_service = _get_web_service(db, user)
        terms = web_service.create_payment_terms(create_data)

        set_flash(response, "Payment terms created successfully", "success")
        return RedirectResponse(
            url=f"/accounting/payment-terms/{terms.id}",
            status_code=303,
        )
    except ValidationError as e:
        web_service.rollback()
        set_flash(response, str(e), "error")
        return RedirectResponse(
            url="/accounting/payment-terms/new",
            status_code=303,
        )


@router.post("/payment-terms/{terms_id}", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def payment_terms_update(
    terms_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf_protect: CSRFProtect,
    db: DB,
):
    """Update payment terms."""
    await validate_csrf(request, csrf_protect)

    form = await request.form()
    service = _get_service(db, user)

    template_name = form_str(form, "template_name") or None
    description = form_str(form, "description") or None
    is_active = form_str(form, "is_active") == "on"

    # Parse schedules from form
    schedules = []
    idx = 0
    while f"schedule_{idx}_percentage" in form:
        schedules.append(ScheduleData(
            credit_days=form_int(form, f"schedule_{idx}_credit_days", 0) or 0,
            credit_months=form_int(form, f"schedule_{idx}_credit_months", 0) or 0,
            day_of_month=form_int(form, f"schedule_{idx}_day_of_month"),
            payment_percentage=form_decimal(form, f"schedule_{idx}_percentage", Decimal("100")) or Decimal("100"),
            discount_percentage=form_decimal(form, f"schedule_{idx}_discount", Decimal("0")) or Decimal("0"),
            discount_days=form_int(form, f"schedule_{idx}_discount_days", 0) or 0,
            description=form_str(form, f"schedule_{idx}_description") or None,
        ))
        idx += 1

    try:
        update_data = PaymentTermsUpdateData(
            template_name=template_name,
            description=description,
            is_active=is_active,
            schedules=schedules if schedules else None,
        )
        web_service = _get_web_service(db, user)
        web_service.update_payment_terms(terms_id, update_data)

        set_flash(response, "Payment terms updated successfully", "success")
        return RedirectResponse(
            url=f"/accounting/payment-terms/{terms_id}",
            status_code=303,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Payment terms not found")
    except ValidationError as e:
        web_service.rollback()
        set_flash(response, str(e), "error")
        return RedirectResponse(
            url=f"/accounting/payment-terms/{terms_id}/edit",
            status_code=303,
        )


@router.post("/payment-terms/{terms_id}/delete", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def payment_terms_delete(
    terms_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_protect: CSRFProtect,
    db: DB,
):
    """Delete (deactivate) payment terms."""
    await validate_csrf(request, csrf_protect)

    web_service = _get_web_service(db, user)

    try:
        web_service.delete_payment_terms(terms_id)
        set_flash(response, "Payment terms deactivated successfully", "success")
    except NotFoundError:
        set_flash(response, "Payment terms not found", "error")

    return RedirectResponse(url="/accounting/payment-terms", status_code=303)
