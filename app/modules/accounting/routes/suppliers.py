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
)
from app.services.accounting import AccountingSettingsService, PayablesService
from app.services.accounting.payables_types import SupplierCreateData, SupplierUpdateData
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter()


def _get_payables_service(db: DB, user: SessionUser) -> PayablesService:
    settings_service = AccountingSettingsService(db, user)
    return PayablesService(db, settings_service, user)


def get_supplier_group_options(service: PayablesService) -> list:
    """Get unique supplier groups for filter dropdown."""
    return [
        {"value": group, "label": group}
        for group in service.list_supplier_groups()
    ]


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
    service = _get_payables_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_supplier_models(
            search=q,
            supplier_group=group,
            include_disabled=False,
            pagination=pagination,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    suppliers = result.items
    total = result.total

    stats = service.get_supplier_stats()
    group_options = get_supplier_group_options(service)

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
    context["stats"] = stats
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
    service = _get_payables_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_supplier_models(
            search=q,
            supplier_group=group,
            include_disabled=False,
            pagination=pagination,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    suppliers = result.items
    total = result.total

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
    service = _get_payables_service(db, user)
    context["group_options"] = get_supplier_group_options(service)
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
        service = _get_payables_service(db, user)
        context["group_options"] = get_supplier_group_options(service)
        context["currency_options"] = get_currency_options()
        template = templates.get_template("modules/accounting/templates/suppliers/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service = _get_payables_service(db, user)
    supplier = service.create_supplier(
        SupplierCreateData(
            supplier_name=form_str(form, "supplier_name"),
            supplier_group=form_str(form, "supplier_group") or None,
            supplier_type=form_str(form, "supplier_type") or None,
            tax_id=form_str(form, "tax_id") or None,
            email_id=form_str(form, "email_id") or None,
            mobile_no=form_str(form, "mobile_no") or None,
            country=form_str(form, "country") or None,
            default_currency=form_str(form, "default_currency") or None,
            payment_terms=form_str(form, "payment_terms") or None,
            supplier_primary_address=form_str(form, "address") or None,
            default_bank_account=form_str(form, "bank_account") or None,
            is_internal_supplier=form.get("is_internal_supplier") == "on",
            disabled=False,
        )
    )
    db.commit()

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
    service = _get_payables_service(db, user)
    try:
        supplier = service.get_supplier_model(supplier_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Supplier not found") from exc

    invoices = service.list_supplier_invoices(supplier.supplier_name, limit=20)
    outstanding = service.get_supplier_outstanding(supplier.supplier_name)

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
    service = _get_payables_service(db, user)
    try:
        supplier = service.get_supplier_model(supplier_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Supplier not found") from exc

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Suppliers", "href": "/accounting/suppliers"},
        {"label": supplier.supplier_name, "href": f"/accounting/suppliers/{supplier_id}"},
        {"label": "Edit", "href": f"/accounting/suppliers/{supplier_id}/edit", "current": True},
    ])
    context["supplier"] = supplier
    context["group_options"] = get_supplier_group_options(service)
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
    service = _get_payables_service(db, user)
    try:
        supplier = service.get_supplier_model(supplier_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Supplier not found") from exc

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
        context["group_options"] = get_supplier_group_options(service)
        context["currency_options"] = get_currency_options()
        template = templates.get_template("modules/accounting/templates/suppliers/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service.update_supplier(
        supplier_id,
        SupplierUpdateData(
            supplier_name=form_str(form, "supplier_name"),
            supplier_group=form_str(form, "supplier_group") or None,
            supplier_type=form_str(form, "supplier_type") or None,
            tax_id=form_str(form, "tax_id") or None,
            email_id=form_str(form, "email_id") or None,
            mobile_no=form_str(form, "mobile_no") or None,
            country=form_str(form, "country") or None,
            default_currency=form_str(form, "default_currency") or None,
            payment_terms=form_str(form, "payment_terms") or None,
            supplier_primary_address=form_str(form, "address") or None,
            default_bank_account=form_str(form, "bank_account") or None,
            is_internal_supplier=form.get("is_internal_supplier") == "on",
        ),
    )
    db.commit()

    set_flash(response, "Supplier updated successfully", "success")
    return RedirectResponse(url=f"/accounting/suppliers/{supplier_id}", status_code=303)
