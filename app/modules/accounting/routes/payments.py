"""
Payment routes for accounting module.
Includes basic payments and AR payments (customer receipts).
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException, validate_csrf, set_flash, form_str, form_int, form_decimal,
    PaymentStatus, PaymentMethod,
    datetime, Decimal,
)
from app.services.accounting import ARPaymentService, APPaymentService, BankingService, ReceivablesService
from app.services.accounting.web_services import AccountingPaymentsWebService
from app.services.accounting.ar_payment_types import AllocationData, PaymentCreateData, PaymentFilters, PaymentUpdateData
from app.services.accounting.ap_payment_types import APPaymentFilters
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams
from app.models.supplier_payment import SupplierPaymentStatus

router = APIRouter()


def _get_payment_service(db: DB, user: SessionUser) -> ARPaymentService:
    return ARPaymentService(db, user)

def _get_ap_payment_service(db: DB, user: SessionUser) -> APPaymentService:
    return APPaymentService(db, user)


def _get_payment_web_service(db: DB, user: SessionUser) -> AccountingPaymentsWebService:
    return AccountingPaymentsWebService(db, _get_payment_service(db, user))


def _get_banking_service(db: DB, user: SessionUser) -> BankingService:
    return BankingService(db, user)


def _get_receivables_service(db: DB, user: SessionUser) -> ReceivablesService:
    from app.services.accounting import AccountingSettingsService

    settings_service = AccountingSettingsService(db, user)
    return ReceivablesService(db, settings_service, user)


def get_payment_method_options():
    """Get method options for payment filter dropdown."""
    return [
        {"value": m.value, "label": m.value.replace("_", " ").title()}
        for m in PaymentMethod
    ]

def get_payment_status_options():
    """Get status options for payment filter dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in PaymentStatus
    ]

def get_ap_payment_status_options():
    """Get status options for supplier payment filter dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in SupplierPaymentStatus
    ]

def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


# =============================================================================
# BASIC PAYMENTS
# =============================================================================

@router.get("/payments", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def payments_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    method: Optional[str] = Query(None, description="Filter by method"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("payment_date", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Payments list page."""
    service = _get_payment_service(db, user)
    method_enum = None
    if method:
        try:
            method_enum = PaymentMethod(method)
        except ValueError:
            method_enum = None

    filters = PaymentFilters(
        search=q,
        payment_method=method_enum,
        sort_by=sort,
        sort_dir=dir,
    )
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_payments(filters, pagination)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payments = result.items
    total = result.total
    stats = service.get_payment_stats()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["payments"] = payments
    context["search_query"] = q or ""
    context["current_method"] = method
    context["method_options"] = get_payment_method_options()
    context["stats"] = stats
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/payments/partials/payments_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Payments"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Finance", "href": "/accounting/invoices"},
        {"label": "Payments"},
    ])

    template = templates.get_template("modules/accounting/templates/payments/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/payments/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def payments_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("payment_date"),
    dir: str = Query("desc"),
):
    """Payments table partial for HTMX updates."""
    return await payments_list(
        request, response, user, csrf_token, db,
        q, method, page, per_page, sort, dir
    )


@router.get("/payments/{payment_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def payment_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    payment_id: int,
):
    """Payment detail page."""
    service = _get_payment_service(db, user)
    try:
        payment = service.get_payment(payment_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = payment.receipt_number or f"PAY-{payment.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Finance", "href": "/accounting/invoices"},
        {"label": "Payments", "href": "/accounting/payments"},
        {"label": payment.receipt_number or f"PAY-{payment.id}"},
    ])
    context["payment"] = payment

    template = templates.get_template("modules/accounting/templates/payments/pages/detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# AR PAYMENTS (Customer Receipts)
# =============================================================================



def _get_ar_payments_result(
    db: DB,
    user: SessionUser,
    *,
    q: Optional[str],
    status: Optional[str],
    method: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    page: int,
    per_page: int,
):
    service = _get_payment_service(db, user)
    status_enum = None
    if status:
        try:
            status_enum = PaymentStatus(status)
        except ValueError:
            status_enum = None

    method_enum = None
    if method:
        try:
            method_enum = PaymentMethod(method)
        except ValueError:
            method_enum = None

    start_dt = _parse_date(date_from)
    end_dt = _parse_date(date_to)

    filters = PaymentFilters(
        search=q,
        status=status_enum,
        payment_method=method_enum,
        start_date=start_dt.date() if start_dt else None,
        end_date=end_dt.date() if end_dt else None,
    )
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_payments(filters, pagination)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


@router.get("/ar-payments", response_class=HTMLResponse)
async def ar_payments_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: None = RequireAccountingRead,
    q: Optional[str] = None,
    status: Optional[str] = None,
    method: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
):
    """AR payments (customer receipts) list page."""
    result = _get_ar_payments_result(
        db,
        user,
        q=q,
        status=status,
        method=method,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
    )
    payments = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["payments"] = payments
    service = _get_payment_service(db, user)
    context["stats"] = service.get_ar_payment_stats()
    context["status_options"] = get_payment_status_options()
    context["method_options"] = get_payment_method_options()
    context["current_search"] = q
    context["current_status"] = status
    context["current_method"] = method
    context["current_date_from"] = date_from
    context["current_date_to"] = date_to
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/ar_payments/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/ar-payments/table", response_class=HTMLResponse)
async def ar_payments_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: None = RequireAccountingRead,
    q: Optional[str] = None,
    status: Optional[str] = None,
    method: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
):
    """AR payments table HTMX partial."""
    result = _get_ar_payments_result(
        db,
        user,
        q=q,
        status=status,
        method=method,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
    )
    payments = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["payments"] = payments
    context["current_search"] = q
    context["current_status"] = status
    context["current_method"] = method
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/ar_payments/partials/payments_table.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# AP PAYMENTS (Supplier Payments)
# =============================================================================


def _get_ap_payments_result(
    db: DB,
    user: SessionUser,
    *,
    status: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    page: int,
    per_page: int,
):
    service = _get_ap_payment_service(db, user)
    status_enum = None
    if status:
        try:
            status_enum = SupplierPaymentStatus(status)
        except ValueError:
            status_enum = None

    start_dt = _parse_date(date_from)
    end_dt = _parse_date(date_to)

    filters = APPaymentFilters(
        status=status_enum,
        start_date=start_dt.date() if start_dt else None,
        end_date=end_dt.date() if end_dt else None,
    )
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_payments(filters, pagination)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result


@router.get("/ap-payments", response_class=HTMLResponse)
async def ap_payments_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: None = RequireAccountingRead,
    q: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
):
    """AP payments (supplier payments) list page."""
    result = _get_ap_payments_result(
        db,
        user,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
    )
    payments = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["payments"] = payments
    context["stats"] = {
        "this_month": 0,
        "pending_amount": 0,
        "draft_count": 0,
        "total_count": total,
    }
    context["status_options"] = get_ap_payment_status_options()
    context["current_search"] = q
    context["current_status"] = status
    context["current_date_from"] = date_from
    context["current_date_to"] = date_to
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/ap_payments/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/ap-payments/table", response_class=HTMLResponse)
async def ap_payments_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: None = RequireAccountingRead,
    q: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
):
    """AP payments table HTMX partial."""
    result = _get_ap_payments_result(
        db,
        user,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
    )
    payments = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["payments"] = payments
    context["current_search"] = q
    context["current_status"] = status
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/ap_payments/partials/payments_table.html")
    return HTMLResponse(template.render(context))


@router.get("/ap-payments/{payment_id}", response_class=HTMLResponse)
async def ap_payment_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    payment_id: int,
    _: None = RequireAccountingRead,
):
    """AP payment detail page."""
    service = _get_ap_payment_service(db, user)
    try:
        payment = service.get_payment(payment_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = payment.payment_number or f"PAY-{payment.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "AP Payments", "href": "/accounting/ap-payments"},
        {"label": payment.payment_number or f"PAY-{payment.id}"},
    ])
    context["payment"] = payment

    template = templates.get_template("modules/accounting/templates/ap_payments/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/ar-payments/new", response_class=HTMLResponse)
async def ar_payment_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    _: None = RequireAccountingWrite,
):
    """New AR payment form."""
    receivables_service = _get_receivables_service(db, user)
    customer_accounts = receivables_service.list_customer_accounts()
    banking_service = _get_banking_service(db, user)
    bank_accounts_result = banking_service.list_bank_accounts_paginated(
        include_disabled=False,
        pagination=PaginationParams(limit=2000, offset=0),
    )
    bank_accounts = bank_accounts_result.items

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["payment"] = None
    context["customer_accounts"] = customer_accounts
    context["bank_accounts"] = bank_accounts
    context["method_options"] = get_payment_method_options()

    template = templates.get_template("modules/accounting/templates/ar_payments/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/ar-payments")
async def ar_payment_create(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    _: None = RequireAccountingWrite,
):
    """Create a new AR payment."""
    form_data = await request.form()
    await validate_csrf(request)

    payment_date_str = form_str(form_data, "payment_date")
    payment_date = datetime.utcnow()
    if payment_date_str:
        try:
            payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d")
        except ValueError:
            payment_date = datetime.utcnow()

    method_value = form_str(form_data, "payment_method")
    service = _get_payment_service(db, user)
    web_service = _get_payment_web_service(db, user)
    try:
        payment = web_service.create_payment(
            PaymentCreateData(
                payment_date=payment_date,
                amount=form_decimal(form_data, "amount", Decimal("0")) or Decimal("0"),
                customer_account_id=form_int(form_data, "customer_account_id"),
                currency=form_str(form_data, "currency", "NGN") or "NGN",
                payment_method=(
                    PaymentMethod(method_value)
                    if method_value
                    else PaymentMethod.BANK_TRANSFER
                ),
                receipt_number=form_str(form_data, "receipt_number") or None,
                transaction_reference=form_str(form_data, "transaction_reference") or None,
                bank_account_id=form_int(form_data, "bank_account_id"),
                notes=form_str(form_data, "notes") or None,
            )
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    set_flash(response, f"Receipt created successfully", "success")
    return RedirectResponse(url=f"/accounting/ar-payments/{payment.id}", status_code=303)


@router.get("/ar-payments/{payment_id}", response_class=HTMLResponse)
async def ar_payment_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    payment_id: int,
    _: None = RequireAccountingRead,
):
    """AR payment detail page."""
    service = _get_payment_service(db, user)
    try:
        payment = service.get_payment_with_relations(
            payment_id,
            include_allocations=True,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["payment"] = payment

    template = templates.get_template("modules/accounting/templates/ar_payments/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/ar-payments/{payment_id}/edit", response_class=HTMLResponse)
async def ar_payment_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    payment_id: int,
    _: None = RequireAccountingWrite,
):
    """Edit AR payment form."""
    service = _get_payment_service(db, user)
    try:
        payment = service.get_payment(payment_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc

    receivables_service = _get_receivables_service(db, user)
    customer_accounts = receivables_service.list_customer_accounts()
    banking_service = _get_banking_service(db, user)
    bank_accounts_result = banking_service.list_bank_accounts_paginated(
        include_disabled=False,
        pagination=PaginationParams(limit=2000, offset=0),
    )
    bank_accounts = bank_accounts_result.items

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["payment"] = payment
    context["customer_accounts"] = customer_accounts
    context["bank_accounts"] = bank_accounts
    context["method_options"] = get_payment_method_options()

    template = templates.get_template("modules/accounting/templates/ar_payments/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/ar-payments/{payment_id}")
async def ar_payment_update(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    payment_id: int,
    _: None = RequireAccountingWrite,
):
    """Update an AR payment."""
    form_data = await request.form()
    await validate_csrf(request)
    payment_date = None
    payment_date_str = form_str(form_data, "payment_date")
    if payment_date_str:
        try:
            payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d")
        except ValueError:
            payment_date = None

    method_value = form_str(form_data, "payment_method")
    method_enum = None
    if method_value:
        try:
            method_enum = PaymentMethod(method_value)
        except ValueError:
            method_enum = None

    service = _get_payment_service(db, user)
    web_service = _get_payment_web_service(db, user)
    try:
        payment = web_service.update_payment(
            payment_id,
            PaymentUpdateData(
                payment_date=payment_date,
                receipt_number=form_str(form_data, "receipt_number") or None,
                customer_account_id=form_int(form_data, "customer_account_id"),
                amount=form_decimal(form_data, "amount"),
                currency=form_str(form_data, "currency") or None,
                payment_method=method_enum,
                transaction_reference=form_str(form_data, "transaction_reference") or None,
                bank_account_id=form_int(form_data, "bank_account_id"),
                notes=form_str(form_data, "notes") or None,
            ),
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    set_flash(response, "Receipt updated successfully", "success")
    return RedirectResponse(url=f"/accounting/ar-payments/{payment.id}", status_code=303)


@router.get("/ar-payments/{payment_id}/allocate", response_class=HTMLResponse)
async def ar_payment_allocate_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    payment_id: int,
    _: None = RequireAccountingWrite,
):
    """AR payment allocation form."""
    service = _get_payment_service(db, user)
    web_service = _get_payment_web_service(db, user)
    try:
        payment = service.get_payment_with_relations(payment_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc

    # Get outstanding invoices for this customer
    outstanding_invoices = []
    if payment.customer_account_id:
        receivables_service = _get_receivables_service(db, user)
        outstanding_invoices = receivables_service.list_outstanding_invoices_for_customer(
            payment.customer_account_id
        )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["payment"] = payment
    context["outstanding_invoices"] = outstanding_invoices
    context["now"] = datetime.utcnow()

    template = templates.get_template("modules/accounting/templates/ar_payments/pages/allocate.html")
    return HTMLResponse(template.render(context))


@router.post("/ar-payments/{payment_id}/allocate")
async def ar_payment_allocate(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    payment_id: int,
    _: None = RequireAccountingWrite,
):
    """Process payment allocation."""
    form_data = await request.form()
    await validate_csrf(request)

    service = _get_payment_service(db, user)
    try:
        payment = service.get_payment(payment_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc

    allocations = []
    for key in form_data.keys():
        if key.startswith("invoice_") and form_data.get(key):
            invoice_id = int(key.replace("invoice_", ""))
            amount = form_decimal(form_data, f"amount_{invoice_id}", Decimal("0")) or Decimal("0")
            discount = form_decimal(form_data, f"discount_{invoice_id}", Decimal("0")) or Decimal("0")
            writeoff = form_decimal(form_data, f"writeoff_{invoice_id}", Decimal("0")) or Decimal("0")

            if amount > 0:
                allocations.append(
                    AllocationData(
                        document_type="invoice",
                        document_id=invoice_id,
                        allocated_amount=amount,
                        discount_amount=discount,
                        write_off_amount=writeoff,
                    )
                )

    if allocations:
        try:
            web_service.add_allocations(payment.id, allocations)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    allocated_total = sum(a.allocated_amount for a in allocations)

    set_flash(response, f"Allocated {allocated_total:.2f} to invoices", "success")
    return RedirectResponse(url=f"/accounting/ar-payments/{payment.id}", status_code=303)


@router.post("/ar-payments/{payment_id}/approve")
async def ar_payment_approve(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    payment_id: int,
    _: None = RequireAccountingWrite,
):
    """Approve an AR payment."""
    form_data = await request.form()
    await validate_csrf(request)

    service = _get_payment_service(db, user)
    web_service = _get_payment_web_service(db, user)
    try:
        payment = web_service.approve_payment(payment_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc

    set_flash(response, "Payment approved", "success")
    return RedirectResponse(url=f"/accounting/ar-payments/{payment.id}", status_code=303)


@router.post("/ar-payments/{payment_id}/post")
async def ar_payment_post(
    request: Request,
    response: Response,
    user: SessionUser,
    db: DB,
    payment_id: int,
    _: None = RequireAccountingWrite,
):
    """Post an AR payment to General Ledger."""
    form_data = await request.form()
    await validate_csrf(request)

    service = _get_payment_service(db, user)
    web_service = _get_payment_web_service(db, user)
    try:
        payment = web_service.post_payment(payment_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc

    set_flash(response, "Payment posted to General Ledger", "success")
    return RedirectResponse(url=f"/accounting/ar-payments/{payment.id}", status_code=303)


# =============================================================================
# AP PAYMENTS (Supplier Payments) - To be implemented
# =============================================================================
# AP payments routes will be added here
