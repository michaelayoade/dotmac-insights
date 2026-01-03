"""
Payments module web routes.

Provides SSR pages for AR (customer) and AP (supplier) payment management.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import date

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.models.supplier_payment import SupplierPayment, SupplierPaymentStatus
from app.models.payment_allocation import PaymentAllocation
from app.models.party import CustomerAccount

router = APIRouter(prefix="/payments", tags=["payments-web"])
templates = get_template_env()

RequirePaymentsRead = Depends(require_scope("payments:read"))
RequirePaymentsWrite = Depends(require_scope("payments:write"))


@router.get("", response_class=HTMLResponse, dependencies=[RequirePaymentsRead])
async def payments_index(request: Request):
    """Redirect to receivables."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/payments/receivables", status_code=302)


# ==================== AR (RECEIVABLES) ====================

@router.get("/receivables", response_class=HTMLResponse, dependencies=[RequirePaymentsRead])
async def ar_payments_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    method: Optional[str] = Query(None, description="Filter by payment method"),
    date_from: Optional[date] = Query(None, description="Payment date from"),
    date_to: Optional[date] = Query(None, description="Payment date to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """AR (customer) payments list page."""
    query = select(Payment).options(
        selectinload(Payment.customer_account).selectinload(CustomerAccount.party),
    )

    if q:
        search = f"%{q}%"
        query = query.where(
            or_(
                Payment.receipt_number.ilike(search),
                Payment.transaction_reference.ilike(search),
            )
        )

    if status:
        try:
            status_enum = PaymentStatus(status.lower())
            query = query.where(Payment.status == status_enum)
        except ValueError:
            pass

    if method:
        try:
            method_enum = PaymentMethod(method.lower())
            query = query.where(Payment.payment_method == method_enum)
        except ValueError:
            pass

    if date_from:
        query = query.where(Payment.payment_date >= date_from)

    if date_to:
        query = query.where(Payment.payment_date <= date_to)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(Payment.payment_date.desc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    payments = result.scalars().all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Customer Payments"
    context["payments"] = payments
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["q"] = q or ""
    context["status_filter"] = status or ""
    context["method_filter"] = method or ""
    context["date_from"] = date_from.isoformat() if date_from else ""
    context["date_to"] = date_to.isoformat() if date_to else ""

    context["status_options"] = [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in PaymentStatus
    ]
    context["method_options"] = [
        {"value": m.value, "label": m.value.replace("_", " ").title()}
        for m in PaymentMethod
    ]

    if request.headers.get("HX-Request"):
        template = templates.get_template("modules/payments/templates/partials/ar_payments_table.html")
    else:
        template = templates.get_template("modules/payments/templates/pages/ar_list.html")

    return HTMLResponse(template.render(context))


@router.get("/receivables/table", response_class=HTMLResponse, dependencies=[RequirePaymentsRead])
async def ar_payments_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """AR payments table partial for HTMX."""
    return await ar_payments_list(
        request, response, user, csrf_token, db,
        q, status, method, date_from, date_to, page, per_page
    )


@router.get("/receivables/{payment_id}", response_class=HTMLResponse, dependencies=[RequirePaymentsRead])
async def ar_payment_detail(
    payment_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """AR payment detail page."""
    query = (
        select(Payment)
        .options(
            selectinload(Payment.customer_account).selectinload(CustomerAccount.party),
            selectinload(Payment.invoice),
            selectinload(Payment.allocations),
        )
        .where(Payment.id == payment_id)
    )
    result = db.execute(query)
    payment = result.scalar_one_or_none()

    if not payment:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Payment not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Payment: {payment.receipt_number or payment.id}"
    context["payment"] = payment

    template = templates.get_template("modules/payments/templates/pages/ar_detail.html")
    return HTMLResponse(template.render(context))


# ==================== AP (PAYABLES) ====================

@router.get("/payables", response_class=HTMLResponse, dependencies=[RequirePaymentsRead])
async def ap_payments_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    supplier_id: Optional[int] = Query(None, description="Filter by supplier"),
    date_from: Optional[date] = Query(None, description="Payment date from"),
    date_to: Optional[date] = Query(None, description="Payment date to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """AP (supplier) payments list page."""
    query = select(SupplierPayment).options(
        selectinload(SupplierPayment.allocations),
    )

    if q:
        search = f"%{q}%"
        query = query.where(
            or_(
                SupplierPayment.payment_number.ilike(search),
                SupplierPayment.supplier_name.ilike(search),
                SupplierPayment.reference_number.ilike(search),
            )
        )

    if status:
        try:
            status_enum = SupplierPaymentStatus(status.lower())
            query = query.where(SupplierPayment.status == status_enum)
        except ValueError:
            pass

    if supplier_id:
        query = query.where(SupplierPayment.supplier_id == supplier_id)

    if date_from:
        query = query.where(SupplierPayment.payment_date >= date_from)

    if date_to:
        query = query.where(SupplierPayment.payment_date <= date_to)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(SupplierPayment.payment_date.desc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    payments = result.scalars().all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Supplier Payments"
    context["payments"] = payments
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["q"] = q or ""
    context["status_filter"] = status or ""
    context["supplier_id_filter"] = supplier_id
    context["date_from"] = date_from.isoformat() if date_from else ""
    context["date_to"] = date_to.isoformat() if date_to else ""

    context["status_options"] = [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in SupplierPaymentStatus
    ]

    if request.headers.get("HX-Request"):
        template = templates.get_template("modules/payments/templates/partials/ap_payments_table.html")
    else:
        template = templates.get_template("modules/payments/templates/pages/ap_list.html")

    return HTMLResponse(template.render(context))


@router.get("/payables/table", response_class=HTMLResponse, dependencies=[RequirePaymentsRead])
async def ap_payments_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    supplier_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """AP payments table partial for HTMX."""
    return await ap_payments_list(
        request, response, user, csrf_token, db,
        q, status, supplier_id, date_from, date_to, page, per_page
    )


@router.get("/payables/{payment_id}", response_class=HTMLResponse, dependencies=[RequirePaymentsRead])
async def ap_payment_detail(
    payment_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """AP payment detail page."""
    query = (
        select(SupplierPayment)
        .options(
            selectinload(SupplierPayment.allocations),
        )
        .where(SupplierPayment.id == payment_id)
    )
    result = db.execute(query)
    payment = result.scalar_one_or_none()

    if not payment:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Payment not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Payment: {payment.payment_number}"
    context["payment"] = payment

    template = templates.get_template("modules/payments/templates/pages/ap_detail.html")
    return HTMLResponse(template.render(context))
