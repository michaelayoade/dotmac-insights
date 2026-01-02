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
    Payment, PaymentStatus, PaymentMethod, Invoice, InvoiceStatus, BankAccount,
    func, or_, datetime, Decimal, timedelta, selectinload,
)
from app.models.party import CustomerAccount, Party

router = APIRouter()


def get_payment_method_options():
    """Get method options for payment filter dropdown."""
    return [
        {"value": m.value, "label": m.value.replace("_", " ").title()}
        for m in PaymentMethod
    ]


def get_payment_stats(db) -> dict:
    """Calculate payment statistics."""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)

    # Total count
    total_count = db.query(func.count(Payment.id)).scalar() or 0

    # This month
    this_month = db.query(func.sum(Payment.amount)).filter(
        Payment.payment_date >= month_start
    ).scalar() or Decimal("0")

    # Last month
    last_month = db.query(func.sum(Payment.amount)).filter(
        Payment.payment_date >= last_month_start,
        Payment.payment_date < month_start
    ).scalar() or Decimal("0")

    # Unallocated
    unallocated = db.query(func.sum(Payment.unallocated_amount)).filter(
        Payment.unallocated_amount > 0
    ).scalar() or Decimal("0")

    return {
        "total_count": total_count,
        "this_month": this_month,
        "last_month": last_month,
        "unallocated": unallocated,
    }


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
    # Build query
    query = db.query(Payment)

    # Search
    if q:
        search_filter = or_(
            Payment.receipt_number.ilike(f"%{q}%"),
            Payment.transaction_reference.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if method:
        query = query.filter(Payment.payment_method == method)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(Payment, sort, Payment.payment_date)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    payments = query.offset(offset).limit(per_page).all()

    # Get stats
    stats = get_payment_stats(db)

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
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

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

def get_ar_payment_stats(db) -> dict:
    """Get AR payment statistics."""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    this_month = db.query(func.sum(Payment.amount)).filter(
        Payment.payment_date >= month_start,
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED])
    ).scalar() or Decimal("0")

    pending_amount = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.PENDING
    ).scalar() or Decimal("0")

    unallocated = db.query(func.sum(Payment.unallocated_amount)).filter(
        Payment.unallocated_amount > 0
    ).scalar() or Decimal("0")

    total_count = db.query(func.count(Payment.id)).scalar() or 0

    return {
        "this_month": this_month,
        "pending_amount": pending_amount,
        "unallocated": unallocated,
        "total_count": total_count,
    }


def get_invoice_status_options():
    """Get status options for invoice filter dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in InvoiceStatus
    ]


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
    query = db.query(Payment).options(
        selectinload(Payment.contact),
        selectinload(Payment.customer)
    )

    if q:
        query = query.filter(
            or_(
                Payment.receipt_number.ilike(f"%{q}%"),
                Payment.transaction_reference.ilike(f"%{q}%")
            )
        )

    if status:
        query = query.filter(Payment.status == PaymentStatus(status))

    if method:
        query = query.filter(Payment.payment_method == PaymentMethod(method))

    if date_from:
        try:
            from_dt = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Payment.payment_date >= from_dt)
        except ValueError:
            pass

    if date_to:
        try:
            to_dt = datetime.strptime(date_to, "%Y-%m-%d")
            to_dt = to_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(Payment.payment_date <= to_dt)
        except ValueError:
            pass

    total = query.count()
    payments = query.order_by(Payment.payment_date.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["payments"] = payments
    context["stats"] = get_ar_payment_stats(db)
    context["status_options"] = get_invoice_status_options()
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
    query = db.query(Payment).options(
        selectinload(Payment.contact),
        selectinload(Payment.customer)
    )

    if q:
        query = query.filter(
            or_(
                Payment.receipt_number.ilike(f"%{q}%"),
                Payment.transaction_reference.ilike(f"%{q}%")
            )
        )

    if status:
        query = query.filter(Payment.status == PaymentStatus(status))

    if method:
        query = query.filter(Payment.payment_method == PaymentMethod(method))

    if date_from:
        try:
            from_dt = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Payment.payment_date >= from_dt)
        except ValueError:
            pass

    if date_to:
        try:
            to_dt = datetime.strptime(date_to, "%Y-%m-%d")
            to_dt = to_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(Payment.payment_date <= to_dt)
        except ValueError:
            pass

    total = query.count()
    payments = query.order_by(Payment.payment_date.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["payments"] = payments
    context["current_search"] = q
    context["current_status"] = status
    context["current_method"] = method
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/ar_payments/partials/payments_table.html")
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
    customer_accounts = (
        db.query(CustomerAccount)
        .join(Party, CustomerAccount.party_id == Party.id)
        .order_by(Party.name)
        .all()
    )
    bank_accounts = db.query(BankAccount).filter(BankAccount.disabled == False).order_by(BankAccount.account_name).all()

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

    from app.models.payment import PaymentSource

    payment_date_str = form_str(form_data, "payment_date")
    payment_date = datetime.utcnow()
    if payment_date_str:
        try:
            payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d")
        except ValueError:
            payment_date = datetime.utcnow()

    method_value = form_str(form_data, "payment_method")

    payment = Payment(
        receipt_number=form_str(form_data, "receipt_number") or None,
        payment_date=payment_date,
        customer_account_id=form_int(form_data, "customer_account_id"),
        amount=form_decimal(form_data, "amount", Decimal("0")) or Decimal("0"),
        currency=form_str(form_data, "currency", "NGN") or "NGN",
        payment_method=PaymentMethod(method_value) if method_value else PaymentMethod.BANK_TRANSFER,
        transaction_reference=form_str(form_data, "transaction_reference") or None,
        bank_account_id=form_int(form_data, "bank_account_id"),
        notes=form_str(form_data, "notes") or None,
        source=PaymentSource.INTERNAL,
        status=PaymentStatus.PENDING,
        created_by_id=user.id,
    )
    payment.unallocated_amount = payment.amount
    db.add(payment)
    db.commit()

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
    payment = db.query(Payment).options(
        selectinload(Payment.customer_account),
        selectinload(Payment.allocations)
    ).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

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
    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    customer_accounts = (
        db.query(CustomerAccount)
        .join(Party, CustomerAccount.party_id == Party.id)
        .order_by(Party.name)
        .all()
    )
    bank_accounts = db.query(BankAccount).filter(BankAccount.disabled == False).order_by(BankAccount.account_name).all()

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

    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment_date_str = form_str(form_data, "payment_date")
    if payment_date_str:
        try:
            payment.payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d")
        except ValueError:
            pass

    receipt_number = form_str(form_data, "receipt_number")
    if receipt_number:
        payment.receipt_number = receipt_number
    customer_account_id = form_int(form_data, "customer_account_id")
    if customer_account_id is not None:
        payment.customer_account_id = customer_account_id
    amount = form_decimal(form_data, "amount", payment.amount)
    if amount is not None:
        payment.amount = amount
    currency = form_str(form_data, "currency", payment.currency)
    if currency:
        payment.currency = currency
    method_value = form_str(form_data, "payment_method")
    if method_value:
        payment.payment_method = PaymentMethod(method_value)
    transaction_reference = form_str(form_data, "transaction_reference")
    if transaction_reference:
        payment.transaction_reference = transaction_reference
    bank_account_id = form_int(form_data, "bank_account_id")
    if bank_account_id is not None:
        payment.bank_account_id = bank_account_id
    notes = form_str(form_data, "notes")
    if notes:
        payment.notes = notes
    payment.updated_by_id = user.id

    db.commit()

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
    payment = db.query(Payment).options(
        selectinload(Payment.customer_account)
    ).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Get outstanding invoices for this customer
    outstanding_invoices = []
    if payment.customer_account_id:
        outstanding_invoices = db.query(Invoice).filter(
            Invoice.customer_account_id == payment.customer_account_id,
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
            Invoice.balance > 0
        ).order_by(Invoice.due_date).all()

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

    from app.models.payment_allocation import PaymentAllocation, AllocationType

    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    total_allocated = Decimal("0")

    # Process each invoice allocation
    for key in form_data.keys():
        if key.startswith("invoice_") and form_data.get(key):
            invoice_id = int(key.replace("invoice_", ""))
            amount = form_decimal(form_data, f"amount_{invoice_id}", Decimal("0")) or Decimal("0")
            discount = form_decimal(form_data, f"discount_{invoice_id}", Decimal("0")) or Decimal("0")
            writeoff = form_decimal(form_data, f"writeoff_{invoice_id}", Decimal("0")) or Decimal("0")

            if amount > 0:
                allocation = PaymentAllocation(
                    payment_id=payment.id,
                    allocation_type=AllocationType.INVOICE,
                    document_id=invoice_id,
                    allocated_amount=amount,
                    discount_amount=discount,
                    write_off_amount=writeoff,
                )
                db.add(allocation)
                total_allocated += amount

                # Update invoice balance
                invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
                if invoice:
                    invoice.amount_paid = (invoice.amount_paid or Decimal("0")) + amount + discount + writeoff
                    invoice.balance = invoice.total_amount - invoice.amount_paid
                    if invoice.balance <= 0:
                        invoice.status = InvoiceStatus.PAID
                    else:
                        invoice.status = InvoiceStatus.PARTIALLY_PAID

    # Update payment allocation totals
    payment.total_allocated = (payment.total_allocated or Decimal("0")) + total_allocated
    payment.unallocated_amount = payment.amount - payment.total_allocated

    db.commit()

    set_flash(response, f"Allocated {total_allocated:.2f} to invoices", "success")
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

    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment.status = PaymentStatus.APPROVED
    db.commit()

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

    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment.status = PaymentStatus.POSTED
    db.commit()

    set_flash(response, "Payment posted to General Ledger", "success")
    return RedirectResponse(url=f"/accounting/ar-payments/{payment.id}", status_code=303)


# =============================================================================
# AP PAYMENTS (Supplier Payments) - To be implemented
# =============================================================================
# AP payments routes will be added here
