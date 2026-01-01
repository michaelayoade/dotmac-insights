"""
Purchasing module web routes.

Provides SSR pages for purchase orders and procurement.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, or_, and_, case
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import date, timedelta
from decimal import Decimal

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import get_base_context, get_navigation_context, build_breadcrumbs
from app.templates.environment import get_template_env
from app.models.purchasing_order import PurchaseOrder, PurchaseOrderStatus
from app.models.accounting import PurchaseInvoice, PurchaseInvoiceStatus, Supplier

router = APIRouter(prefix="/purchasing", tags=["purchasing-web"])
templates = get_template_env()

RequirePurchasingRead = Depends(require_scope("purchasing:read"))
RequirePurchasingWrite = Depends(require_scope("purchasing:write"))


@router.get("/dashboard", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def purchasing_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Purchasing dashboard - AP overview and key metrics."""
    today = date.today()
    week_end = today + timedelta(days=7)

    # Total outstanding AP
    total_outstanding = db.execute(
        select(func.sum(PurchaseInvoice.outstanding_amount)).where(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.status.in_([
                PurchaseInvoiceStatus.SUBMITTED,
                PurchaseInvoiceStatus.UNPAID,
                PurchaseInvoiceStatus.OVERDUE,
            ])
        )
    ).scalar() or Decimal("0")

    # Bills count by status
    bills_by_status = db.execute(
        select(
            PurchaseInvoice.status,
            func.count(PurchaseInvoice.id).label("count"),
            func.sum(PurchaseInvoice.grand_total).label("total"),
        ).group_by(PurchaseInvoice.status)
    ).all()

    status_breakdown = {}
    for row in bills_by_status:
        status_val = row.status.value if row.status else "unknown"
        status_breakdown[status_val] = {
            "count": row.count,
            "total": float(row.total or 0),
        }

    # Overdue amounts
    total_overdue = db.execute(
        select(func.sum(PurchaseInvoice.outstanding_amount)).where(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.due_date < today,
            PurchaseInvoice.status.in_([
                PurchaseInvoiceStatus.SUBMITTED,
                PurchaseInvoiceStatus.UNPAID,
                PurchaseInvoiceStatus.OVERDUE,
            ])
        )
    ).scalar() or Decimal("0")

    # Overdue bills count
    overdue_count = db.execute(
        select(func.count(PurchaseInvoice.id)).where(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.due_date < today,
        )
    ).scalar() or 0

    # Bills due this week
    due_this_week = db.execute(
        select(
            func.count(PurchaseInvoice.id),
            func.sum(PurchaseInvoice.outstanding_amount),
        ).where(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.due_date >= today,
            PurchaseInvoice.due_date <= week_end,
        )
    ).first()

    due_this_week_count = int(due_this_week[0] or 0) if due_this_week else 0
    due_this_week_total = float(due_this_week[1] or 0) if due_this_week else 0

    # Supplier count
    supplier_count = db.execute(
        select(func.count(Supplier.id)).where(Supplier.disabled == False)
    ).scalar() or 0

    # Top 5 suppliers by outstanding
    top_suppliers = db.execute(
        select(
            PurchaseInvoice.supplier_name,
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
            func.count(PurchaseInvoice.id).label("bill_count"),
        ).where(
            PurchaseInvoice.outstanding_amount > 0,
        ).group_by(
            PurchaseInvoice.supplier_name
        ).order_by(
            func.sum(PurchaseInvoice.outstanding_amount).desc()
        ).limit(5)
    ).all()

    # Recent unpaid bills
    recent_unpaid_bills = db.execute(
        select(PurchaseInvoice).where(
            PurchaseInvoice.outstanding_amount > 0,
        ).order_by(PurchaseInvoice.posting_date.desc()).limit(10)
    ).scalars().all()

    # Overdue bills requiring attention
    overdue_bills = db.execute(
        select(PurchaseInvoice).where(
            PurchaseInvoice.outstanding_amount > 0,
            PurchaseInvoice.due_date < today,
        ).order_by(PurchaseInvoice.due_date.asc()).limit(10)
    ).scalars().all()

    # Purchase orders stats
    po_stats = db.execute(
        select(
            func.count(PurchaseOrder.id).label("total"),
            func.sum(case((PurchaseOrder.status == PurchaseOrderStatus.DRAFT, 1), else_=0)).label("draft"),
            func.sum(case((PurchaseOrder.status == PurchaseOrderStatus.TO_RECEIVE, 1), else_=0)).label("to_receive"),
            func.sum(case((PurchaseOrder.status == PurchaseOrderStatus.COMPLETED, 1), else_=0)).label("completed"),
        )
    ).first()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Purchasing Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Dashboard"},
    ])

    context["stats"] = {
        "total_outstanding": total_outstanding,
        "total_overdue": total_overdue,
        "overdue_count": overdue_count,
        "overdue_percentage": round(float(total_overdue / total_outstanding * 100), 1) if total_outstanding > 0 else 0,
        "supplier_count": supplier_count,
        "due_this_week_count": due_this_week_count,
        "due_this_week_total": due_this_week_total,
    }

    context["status_breakdown"] = status_breakdown
    context["top_suppliers"] = [
        {
            "name": row.supplier_name,
            "outstanding": float(row.outstanding),
            "bill_count": row.bill_count,
        }
        for row in top_suppliers
    ]
    context["recent_unpaid_bills"] = recent_unpaid_bills
    context["overdue_bills"] = overdue_bills

    context["po_stats"] = {
        "total": po_stats.total if po_stats else 0,
        "draft": po_stats.draft if po_stats else 0,
        "to_receive": po_stats.to_receive if po_stats else 0,
        "completed": po_stats.completed if po_stats else 0,
    }

    template = templates.get_template("modules/purchasing/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def purchase_orders_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    supplier: Optional[str] = Query(None, description="Filter by supplier"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("transaction_date", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Purchase orders list page."""
    # Base query
    query = select(PurchaseOrder)

    # Search
    if q:
        search = f"%{q}%"
        query = query.where(
            or_(
                PurchaseOrder.erpnext_id.ilike(search),
                PurchaseOrder.supplier_name.ilike(search),
                PurchaseOrder.supplier.ilike(search),
            )
        )

    # Filters
    if status:
        try:
            status_enum = PurchaseOrderStatus(status)
            query = query.where(PurchaseOrder.status == status_enum)
        except ValueError:
            pass

    if supplier:
        query = query.where(PurchaseOrder.supplier_name.ilike(f"%{supplier}%"))

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    # Sorting
    sort_column = getattr(PurchaseOrder, sort, PurchaseOrder.transaction_date)
    if dir == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    orders = result.scalars().all()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Purchase Orders"
    context["orders"] = orders
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["q"] = q or ""
    context["status_filter"] = status or ""
    context["supplier_filter"] = supplier or ""
    context["sort"] = sort
    context["dir"] = dir

    # Status options for filter
    context["status_options"] = [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in PurchaseOrderStatus
    ]

    # Check if HTMX request
    if request.headers.get("HX-Request"):
        template = templates.get_template("modules/purchasing/templates/partials/orders_table.html")
    else:
        template = templates.get_template("modules/purchasing/templates/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def purchase_orders_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    supplier: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("transaction_date"),
    dir: str = Query("desc"),
):
    """Purchase orders table partial for HTMX."""
    # Reuse list logic
    return await purchase_orders_list(
        request, response, user, csrf_token, db,
        q, status, supplier, page, per_page, sort, dir
    )


@router.get("/{order_id}", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def purchase_order_detail(
    order_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Purchase order detail page."""
    query = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(PurchaseOrder.id == order_id)
    )
    result = db.execute(query)
    order = result.scalar_one_or_none()

    if not order:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Purchase order not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"PO: {order.erpnext_id or order.id}"
    context["order"] = order

    template = templates.get_template("modules/purchasing/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


# ============= BILLS (Purchase Invoices) =============

@router.get("/bills", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def bills_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    supplier: Optional[str] = Query(None, description="Filter by supplier"),
    overdue: Optional[bool] = Query(None, description="Show overdue only"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("posting_date", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Bills (Purchase Invoices) list page."""
    today = date.today()

    # Base query
    query = select(PurchaseInvoice)

    # Search
    if q:
        search = f"%{q}%"
        query = query.where(
            or_(
                PurchaseInvoice.erpnext_id.ilike(search),
                PurchaseInvoice.supplier_name.ilike(search),
                PurchaseInvoice.supplier.ilike(search),
            )
        )

    # Filters
    if status:
        try:
            status_enum = PurchaseInvoiceStatus(status.lower())
            query = query.where(PurchaseInvoice.status == status_enum)
        except ValueError:
            pass

    if supplier:
        query = query.where(PurchaseInvoice.supplier_name.ilike(f"%{supplier}%"))

    if overdue:
        query = query.where(
            PurchaseInvoice.due_date < today,
            PurchaseInvoice.outstanding_amount > 0,
        )

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    # Sorting
    sort_column = getattr(PurchaseInvoice, sort, PurchaseInvoice.posting_date)
    if dir == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    bills = result.scalars().all()

    # Stats
    stats = db.execute(
        select(
            func.count(PurchaseInvoice.id).label("total"),
            func.sum(PurchaseInvoice.grand_total).label("total_amount"),
            func.sum(PurchaseInvoice.outstanding_amount).label("outstanding"),
            func.sum(
                case(
                    (and_(PurchaseInvoice.due_date < today, PurchaseInvoice.outstanding_amount > 0), PurchaseInvoice.outstanding_amount),
                    else_=Decimal("0")
                )
            ).label("overdue_amount"),
        )
    ).first()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Bills"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Bills"},
    ])

    context["bills"] = bills
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["q"] = q or ""
    context["status_filter"] = status or ""
    context["supplier_filter"] = supplier or ""
    context["overdue_filter"] = overdue or False
    context["sort"] = sort
    context["dir"] = dir
    context["today"] = today

    context["stats"] = {
        "total_bills": stats.total if stats else 0,
        "total_amount": float(stats.total_amount or 0) if stats else 0,
        "outstanding": float(stats.outstanding or 0) if stats else 0,
        "overdue_amount": float(stats.overdue_amount or 0) if stats else 0,
    }

    # Status options for filter
    context["status_options"] = [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in PurchaseInvoiceStatus
    ]

    # Check if HTMX request
    if request.headers.get("HX-Request"):
        template = templates.get_template("modules/purchasing/templates/partials/bills_table.html")
    else:
        template = templates.get_template("modules/purchasing/templates/pages/bills_list.html")

    return HTMLResponse(template.render(context))


@router.get("/bills/table", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def bills_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    supplier: Optional[str] = Query(None),
    overdue: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("posting_date"),
    dir: str = Query("desc"),
):
    """Bills table partial for HTMX."""
    return await bills_list(
        request, response, user, csrf_token, db,
        q, status, supplier, overdue, page, per_page, sort, dir
    )


@router.get("/bills/{bill_id}", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def bill_detail(
    bill_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Bill detail page."""
    from app.models.accounting import GLEntry
    from app.models.document_lines import BillLine

    bill = db.execute(
        select(PurchaseInvoice).where(PurchaseInvoice.id == bill_id)
    ).scalar_one_or_none()

    if not bill:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Bill not found"
        return HTMLResponse(template.render(context), status_code=404)

    # Get line items
    items = db.execute(
        select(BillLine).where(
            BillLine.purchase_invoice_id == bill_id
        )
    ).scalars().all()

    # Get related GL entries
    gl_entries: list[GLEntry] = []
    if bill.erpnext_id:
        gl_entries = list(db.execute(
            select(GLEntry).where(
                GLEntry.voucher_type == "Purchase Invoice",
                GLEntry.voucher_no == bill.erpnext_id,
            ).order_by(GLEntry.posting_date.desc())
        ).scalars().all())

    # Calculate days overdue
    today = date.today()
    is_overdue = False
    days_overdue = 0
    if bill.due_date and bill.outstanding_amount and bill.outstanding_amount > 0:
        due_dt = bill.due_date.date() if hasattr(bill.due_date, 'date') else bill.due_date
        if due_dt < today:
            is_overdue = True
            days_overdue = (today - due_dt).days

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Bill: {bill.erpnext_id or bill.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Bills", "href": "/purchasing/bills"},
        {"label": bill.erpnext_id or f"Bill #{bill.id}"},
    ])

    context["bill"] = bill
    context["items"] = items
    context["gl_entries"] = gl_entries
    context["is_overdue"] = is_overdue
    context["days_overdue"] = days_overdue
    context["today"] = today

    template = templates.get_template("modules/purchasing/templates/pages/bill_detail.html")
    return HTMLResponse(template.render(context))
