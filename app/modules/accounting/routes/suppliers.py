"""
Suppliers routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException, set_flash, validate_csrf, form_str,
    Supplier, PurchaseInvoice,
    func, or_, datetime, Decimal,
)

router = APIRouter()


def get_supplier_group_options(db) -> list:
    """Get unique supplier groups for filter dropdown."""
    groups = db.query(Supplier.supplier_group).filter(
        Supplier.supplier_group.isnot(None),
        Supplier.disabled == False,
    ).distinct().all()
    return [{"value": g[0], "label": g[0]} for g in groups if g[0]]


def get_currency_options() -> list:
    """Get common currency options."""
    return [
        {"value": "NGN", "label": "NGN - Nigerian Naira"},
        {"value": "USD", "label": "USD - US Dollar"},
        {"value": "EUR", "label": "EUR - Euro"},
        {"value": "GBP", "label": "GBP - British Pound"},
        {"value": "CAD", "label": "CAD - Canadian Dollar"},
        {"value": "AUD", "label": "AUD - Australian Dollar"},
    ]


@router.get("/suppliers", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def suppliers_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    group: Optional[str] = Query(None, description="Supplier group filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Suppliers list page."""
    query = db.query(Supplier).filter(Supplier.disabled == False)

    if q:
        query = query.filter(
            or_(
                Supplier.supplier_name.ilike(f"%{q}%"),
                Supplier.email_id.ilike(f"%{q}%"),
                Supplier.tax_id.ilike(f"%{q}%"),
            )
        )

    if group:
        query = query.filter(Supplier.supplier_group == group)

    total = query.count()
    query = query.order_by(Supplier.supplier_name)
    suppliers = query.offset((page - 1) * per_page).limit(per_page).all()

    # Stats
    total_suppliers = db.query(func.count(Supplier.id)).filter(Supplier.disabled == False).scalar() or 0
    active_suppliers = db.query(func.count(Supplier.id)).filter(
        Supplier.disabled == False,
        Supplier.on_hold == False,
    ).scalar() or 0

    # Calculate total payables and overdue
    total_payables = db.query(func.sum(PurchaseInvoice.outstanding_amount)).filter(
        PurchaseInvoice.outstanding_amount > 0,
    ).scalar() or Decimal("0")

    now = datetime.utcnow().date()
    total_overdue = db.query(func.sum(PurchaseInvoice.outstanding_amount)).filter(
        PurchaseInvoice.outstanding_amount > 0,
        PurchaseInvoice.due_date < now,
    ).scalar() or Decimal("0")

    # Get unique supplier groups for filter
    group_options = get_supplier_group_options(db)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Suppliers", "href": "/accounting/suppliers", "current": True},
    ])
    context["suppliers"] = suppliers
    context["current_search"] = q or ""
    context["current_group"] = group or ""
    context["group_options"] = group_options
    context["stats"] = {
        "total_suppliers": total_suppliers,
        "active_suppliers": active_suppliers,
        "total_payables": total_payables,
        "total_overdue": total_overdue,
    }
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/suppliers/partials/suppliers_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/suppliers/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/suppliers/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def suppliers_table_partial(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    group: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Suppliers table HTMX partial."""
    query = db.query(Supplier).filter(Supplier.disabled == False)

    if q:
        query = query.filter(
            or_(
                Supplier.supplier_name.ilike(f"%{q}%"),
                Supplier.email_id.ilike(f"%{q}%"),
                Supplier.tax_id.ilike(f"%{q}%"),
            )
        )

    if group:
        query = query.filter(Supplier.supplier_group == group)

    total = query.count()
    suppliers = query.order_by(Supplier.supplier_name).offset((page - 1) * per_page).limit(per_page).all()

    context = get_base_context(request, response, user, csrf_token)
    context["suppliers"] = suppliers
    context["current_search"] = q
    context["current_group"] = group
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/suppliers/partials/suppliers_table.html")
    return HTMLResponse(template.render(context))


@router.get("/suppliers/new", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def supplier_new_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New supplier form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Suppliers", "href": "/accounting/suppliers"},
        {"label": "New Supplier", "href": "/accounting/suppliers/new", "current": True},
    ])
    context["group_options"] = get_supplier_group_options(db)
    context["currency_options"] = get_currency_options()

    template = templates.get_template("modules/accounting/templates/suppliers/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/suppliers", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def supplier_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Create new supplier."""
    form = await request.form()
    await validate_csrf(request)

    errors = {}
    if not form_str(form, "supplier_name"):
        errors["supplier_name"] = "Supplier name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Accounting", "href": "/accounting/invoices"},
            {"label": "Suppliers", "href": "/accounting/suppliers"},
            {"label": "New Supplier", "href": "/accounting/suppliers/new", "current": True},
        ])
        context["errors"] = errors
        context["form_data"] = dict(form)
        context["group_options"] = get_supplier_group_options(db)
        context["currency_options"] = get_currency_options()
        template = templates.get_template("modules/accounting/templates/suppliers/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    supplier = Supplier(
        supplier_name=form_str(form, "supplier_name"),
        supplier_group=form_str(form, "supplier_group") or None,
        tax_id=form_str(form, "tax_id") or None,
        email_id=form_str(form, "email_id") or None,
        mobile_no=form_str(form, "mobile_no") or None,
        country=form_str(form, "country") or None,
        default_currency=form_str(form, "default_currency") or None,
        payment_terms=form_str(form, "payment_terms") or None,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    set_flash(response, "Supplier created successfully", "success")
    return RedirectResponse(url=f"/accounting/suppliers/{supplier.id}", status_code=303)


@router.get("/suppliers/{supplier_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def supplier_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    supplier_id: int,
):
    """Supplier detail page."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Get purchase invoices for this supplier
    invoices = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.supplier == supplier.supplier_name,
        ).order_by(PurchaseInvoice.posting_date.desc()).limit(20).all()

    # Calculate outstanding
    outstanding = db.query(func.sum(PurchaseInvoice.outstanding_amount)).filter(
        PurchaseInvoice.supplier == supplier.supplier_name,
        PurchaseInvoice.outstanding_amount > 0,
    ).scalar() or Decimal("0")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Suppliers", "href": "/accounting/suppliers"},
        {"label": supplier.supplier_name, "href": f"/accounting/suppliers/{supplier_id}", "current": True},
    ])
    context["supplier"] = supplier
    context["bills"] = invoices
    context["stats"] = {
        "total_bills": len(invoices),
        "total_billed": sum((inv.grand_total or Decimal("0")) for inv in invoices),
        "total_paid": sum(((inv.grand_total or Decimal("0")) - (inv.outstanding_amount or Decimal("0"))) for inv in invoices),
        "outstanding": outstanding,
    }

    template = templates.get_template("modules/accounting/templates/suppliers/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/suppliers/{supplier_id}/edit", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def supplier_edit_form(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    supplier_id: int,
):
    """Edit supplier form."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Suppliers", "href": "/accounting/suppliers"},
        {"label": supplier.supplier_name, "href": f"/accounting/suppliers/{supplier_id}"},
        {"label": "Edit", "href": f"/accounting/suppliers/{supplier_id}/edit", "current": True},
    ])
    context["supplier"] = supplier
    context["group_options"] = get_supplier_group_options(db)
    context["currency_options"] = get_currency_options()

    template = templates.get_template("modules/accounting/templates/suppliers/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/suppliers/{supplier_id}", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def supplier_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    supplier_id: int,
):
    """Update supplier."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    form = await request.form()
    await validate_csrf(request)

    errors = {}
    if not form_str(form, "supplier_name"):
        errors["supplier_name"] = "Supplier name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Accounting", "href": "/accounting/invoices"},
            {"label": "Suppliers", "href": "/accounting/suppliers"},
            {"label": supplier.supplier_name, "href": f"/accounting/suppliers/{supplier_id}"},
            {"label": "Edit", "href": f"/accounting/suppliers/{supplier_id}/edit", "current": True},
        ])
        context["supplier"] = supplier
        context["errors"] = errors
        context["form_data"] = dict(form)
        context["group_options"] = get_supplier_group_options(db)
        context["currency_options"] = get_currency_options()
        template = templates.get_template("modules/accounting/templates/suppliers/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    supplier.supplier_name = form_str(form, "supplier_name")
    supplier.supplier_group = form_str(form, "supplier_group") or None
    supplier.tax_id = form_str(form, "tax_id") or None
    supplier.email_id = form_str(form, "email_id") or None
    supplier.mobile_no = form_str(form, "mobile_no") or None
    supplier.country = form_str(form, "country") or None
    supplier.default_currency = form_str(form, "default_currency", supplier.default_currency) or supplier.default_currency
    supplier.payment_terms = form_str(form, "payment_terms") or None
    db.commit()

    set_flash(response, "Supplier updated successfully", "success")
    return RedirectResponse(url=f"/accounting/suppliers/{supplier_id}", status_code=303)
