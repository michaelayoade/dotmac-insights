"""
Suppliers module web routes.

Provides SSR pages for supplier/vendor management and bills.
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
from app.models.accounting import Supplier, SupplierGroup, PurchaseInvoice, PurchaseInvoiceStatus

router = APIRouter(prefix="/suppliers", tags=["suppliers-web"])
templates = get_template_env()

RequireSuppliersRead = Depends(require_scope("purchasing:read"))
RequireSuppliersWrite = Depends(require_scope("purchasing:write"))


@router.get("", response_class=HTMLResponse, dependencies=[RequireSuppliersRead])
async def suppliers_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    group: Optional[str] = Query(None, description="Filter by group"),
    status: Optional[str] = Query(None, description="Filter by status (active/inactive)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("supplier_name", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Suppliers list page."""
    query = select(Supplier).options(selectinload(Supplier.supplier_group_rel))

    # Search
    if q:
        search = f"%{q}%"
        query = query.where(
            or_(
                Supplier.supplier_name.ilike(search),
                Supplier.email_id.ilike(search),
                Supplier.tax_id.ilike(search),
            )
        )

    # Filters
    if group:
        query = query.where(Supplier.supplier_group == group)

    if status == "active":
        query = query.where(Supplier.disabled == False)
    elif status == "inactive":
        query = query.where(Supplier.disabled == True)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    # Sorting
    sort_column = getattr(Supplier, sort, Supplier.supplier_name)
    if dir == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    suppliers = result.scalars().all()

    # Get supplier groups for filter
    groups_query = select(SupplierGroup.name).distinct().order_by(SupplierGroup.name)
    groups_result = db.execute(groups_query)
    supplier_groups = [g[0] for g in groups_result.fetchall() if g[0]]

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Suppliers"
    context["suppliers"] = suppliers
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["q"] = q or ""
    context["group_filter"] = group or ""
    context["status_filter"] = status or ""
    context["sort"] = sort
    context["dir"] = dir
    context["supplier_groups"] = supplier_groups

    if request.headers.get("HX-Request"):
        template = templates.get_template("modules/suppliers/templates/partials/suppliers_table.html")
    else:
        template = templates.get_template("modules/suppliers/templates/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireSuppliersRead])
async def suppliers_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    group: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("supplier_name"),
    dir: str = Query("asc"),
):
    """Suppliers table partial for HTMX."""
    return await suppliers_list(
        request, response, user, csrf_token, db,
        q, group, status, page, per_page, sort, dir
    )


@router.get("/bills", response_class=HTMLResponse, dependencies=[RequireSuppliersRead])
async def bills_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    supplier_id: Optional[int] = Query(None, description="Filter by supplier"),
    date_from: Optional[date] = Query(None, description="Bill date from"),
    date_to: Optional[date] = Query(None, description="Bill date to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Bills (purchase invoices) list page."""
    query = select(PurchaseInvoice)

    if q:
        search = f"%{q}%"
        query = query.where(
            or_(
                PurchaseInvoice.erpnext_id.ilike(search),
                PurchaseInvoice.supplier_name.ilike(search),
            )
        )

    if status:
        try:
            status_enum = PurchaseInvoiceStatus(status.upper())
            query = query.where(PurchaseInvoice.status == status_enum)
        except ValueError:
            pass

    if supplier_id:
        query = query.where(PurchaseInvoice.supplier_id == supplier_id)

    if date_from:
        query = query.where(PurchaseInvoice.posting_date >= date_from)

    if date_to:
        query = query.where(PurchaseInvoice.posting_date <= date_to)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(PurchaseInvoice.posting_date.desc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    bills = result.scalars().all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Bills"
    context["bills"] = bills
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
        {"value": s.value.lower(), "label": s.value.replace("_", " ").title()}
        for s in PurchaseInvoiceStatus
    ]

    if request.headers.get("HX-Request"):
        template = templates.get_template("modules/suppliers/templates/partials/bills_table.html")
    else:
        template = templates.get_template("modules/suppliers/templates/pages/bills_list.html")

    return HTMLResponse(template.render(context))


@router.get("/{supplier_id}", response_class=HTMLResponse, dependencies=[RequireSuppliersRead])
async def supplier_detail(
    supplier_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Supplier detail page."""
    query = (
        select(Supplier)
        .options(selectinload(Supplier.supplier_group_rel))
        .where(Supplier.id == supplier_id)
    )
    result = db.execute(query)
    supplier = result.scalar_one_or_none()

    if not supplier:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Supplier not found"
        return HTMLResponse(template.render(context), status_code=404)

    # Get recent bills
    bills_query = (
        select(PurchaseInvoice)
        .where(PurchaseInvoice.supplier_id == supplier_id)
        .order_by(PurchaseInvoice.posting_date.desc())
        .limit(10)
    )
    bills_result = db.execute(bills_query)
    recent_bills = bills_result.scalars().all()

    # Get outstanding amount
    outstanding_query = (
        select(func.sum(PurchaseInvoice.outstanding_amount))
        .where(PurchaseInvoice.supplier_id == supplier_id)
        .where(PurchaseInvoice.status.in_([PurchaseInvoiceStatus.SUBMITTED, PurchaseInvoiceStatus.UNPAID, PurchaseInvoiceStatus.OVERDUE]))
    )
    outstanding = db.scalar(outstanding_query) or 0

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Supplier: {supplier.supplier_name}"
    context["supplier"] = supplier
    context["recent_bills"] = recent_bills
    context["outstanding_amount"] = outstanding

    template = templates.get_template("modules/suppliers/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/bills/{bill_id}", response_class=HTMLResponse, dependencies=[RequireSuppliersRead])
async def bill_detail(
    bill_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Bill (purchase invoice) detail page."""
    query = (
        select(PurchaseInvoice)
        .options(selectinload(PurchaseInvoice.lines))
        .where(PurchaseInvoice.id == bill_id)
    )
    result = db.execute(query)
    bill = result.scalar_one_or_none()

    if not bill:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Bill not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Bill: {bill.erpnext_id or bill.id}"
    context["bill"] = bill

    template = templates.get_template("modules/suppliers/templates/pages/bill_detail.html")
    return HTMLResponse(template.render(context))
