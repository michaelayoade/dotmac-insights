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

# Allowed sort columns to prevent SQL injection via getattr
ALLOWED_PO_SORTS = {"transaction_date", "name", "supplier_name", "status", "grand_total"}
ALLOWED_PI_SORTS = {"posting_date", "name", "supplier_name", "status", "grand_total", "due_date"}


@router.get("", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
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
    context["today"] = today

    template = templates.get_template("modules/purchasing/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("/orders", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
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

    # Sorting - validate sort column against whitelist to prevent SQL injection
    if sort not in ALLOWED_PO_SORTS:
        sort = "transaction_date"
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


@router.get("/orders/table", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
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


@router.get("/orders/{order_id}", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
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

    # Sorting - validate sort column against whitelist to prevent SQL injection
    if sort not in ALLOWED_PI_SORTS:
        sort = "posting_date"
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


# ============= AGING REPORT =============

@router.get("/aging", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def ap_aging_report(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """AP Aging Report - aged payables by supplier."""
    today = date.today()

    # Get all unpaid bills grouped by supplier with aging buckets
    aging_case_current = case(
        (PurchaseInvoice.due_date >= today, PurchaseInvoice.outstanding_amount),
        else_=Decimal("0")
    )
    aging_case_1_30 = case(
        (and_(PurchaseInvoice.due_date < today, PurchaseInvoice.due_date >= today - timedelta(days=30)), PurchaseInvoice.outstanding_amount),
        else_=Decimal("0")
    )
    aging_case_31_60 = case(
        (and_(PurchaseInvoice.due_date < today - timedelta(days=30), PurchaseInvoice.due_date >= today - timedelta(days=60)), PurchaseInvoice.outstanding_amount),
        else_=Decimal("0")
    )
    aging_case_61_90 = case(
        (and_(PurchaseInvoice.due_date < today - timedelta(days=60), PurchaseInvoice.due_date >= today - timedelta(days=90)), PurchaseInvoice.outstanding_amount),
        else_=Decimal("0")
    )
    aging_case_over_90 = case(
        (PurchaseInvoice.due_date < today - timedelta(days=90), PurchaseInvoice.outstanding_amount),
        else_=Decimal("0")
    )

    aging_by_supplier = db.execute(
        select(
            PurchaseInvoice.supplier_name,
            func.count(PurchaseInvoice.id).label("bill_count"),
            func.sum(PurchaseInvoice.outstanding_amount).label("total"),
            func.sum(aging_case_current).label("current"),
            func.sum(aging_case_1_30).label("days_1_30"),
            func.sum(aging_case_31_60).label("days_31_60"),
            func.sum(aging_case_61_90).label("days_61_90"),
            func.sum(aging_case_over_90).label("over_90"),
        ).where(
            PurchaseInvoice.outstanding_amount > 0,
        ).group_by(
            PurchaseInvoice.supplier_name
        ).order_by(
            func.sum(PurchaseInvoice.outstanding_amount).desc()
        )
    ).all()

    # Summary totals
    summary = db.execute(
        select(
            func.count(PurchaseInvoice.id).label("total_bills"),
            func.sum(PurchaseInvoice.outstanding_amount).label("total"),
            func.sum(aging_case_current).label("current"),
            func.sum(aging_case_1_30).label("days_1_30"),
            func.sum(aging_case_31_60).label("days_31_60"),
            func.sum(aging_case_61_90).label("days_61_90"),
            func.sum(aging_case_over_90).label("over_90"),
        ).where(
            PurchaseInvoice.outstanding_amount > 0,
        )
    ).first()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "AP Aging Report"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Aging Report"},
    ])

    context["aging_data"] = [
        {
            "supplier": row.supplier_name or "Unknown",
            "bill_count": row.bill_count,
            "total": float(row.total or 0),
            "current": float(row.current or 0),
            "days_1_30": float(row.days_1_30 or 0),
            "days_31_60": float(row.days_31_60 or 0),
            "days_61_90": float(row.days_61_90 or 0),
            "over_90": float(row.over_90 or 0),
        }
        for row in aging_by_supplier
    ]

    context["summary"] = {
        "total_bills": summary.total_bills if summary else 0,
        "total": float(summary.total or 0) if summary else 0,
        "current": float(summary.current or 0) if summary else 0,
        "days_1_30": float(summary.days_1_30 or 0) if summary else 0,
        "days_31_60": float(summary.days_31_60 or 0) if summary else 0,
        "days_61_90": float(summary.days_61_90 or 0) if summary else 0,
        "over_90": float(summary.over_90 or 0) if summary else 0,
    }

    context["today"] = today

    template = templates.get_template("modules/purchasing/templates/pages/aging.html")
    return HTMLResponse(template.render(context))


# ============= EXPENSES =============

@router.get("/expenses", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def expenses_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Expenses list - categorized purchasing expenses."""
    from app.models.expense import Expense

    today = date.today()
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    # Query expenses
    query = select(Expense).order_by(Expense.posting_date.desc())
    count_query = select(func.count()).select_from(Expense)
    total = db.scalar(count_query) or 0

    offset = (page - 1) * per_page
    expenses = db.execute(query.offset(offset).limit(per_page)).scalars().all()

    # Stats
    mtd_total = db.execute(
        select(func.sum(Expense.total_claimed_amount)).where(
            Expense.posting_date >= start_of_month
        )
    ).scalar() or Decimal("0")

    ytd_total = db.execute(
        select(func.sum(Expense.total_claimed_amount)).where(
            Expense.posting_date >= start_of_year
        )
    ).scalar() or Decimal("0")

    # By category (top 10)
    by_category = db.execute(
        select(
            Expense.expense_type,
            func.count(Expense.id).label("count"),
            func.sum(Expense.total_claimed_amount).label("total"),
        ).where(
            Expense.posting_date >= start_of_year
        ).group_by(Expense.expense_type).order_by(
            func.sum(Expense.total_claimed_amount).desc()
        ).limit(10)
    ).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Expenses"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Expenses"},
    ])

    context["expenses"] = expenses
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page

    context["stats"] = {
        "mtd_total": mtd_total,
        "ytd_total": ytd_total,
        "total_expenses": total,
    }

    context["by_category"] = [
        {"category": row.expense_type or "Uncategorized", "count": row.count, "total": float(row.total or 0)}
        for row in by_category
    ]

    template = templates.get_template("modules/purchasing/templates/pages/expenses.html")
    return HTMLResponse(template.render(context))


# ============= DEBIT NOTES =============

@router.get("/debit-notes", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def debit_notes_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Debit Notes list - supplier returns and adjustments."""
    from app.models.books_settings import DebitNote

    query = select(DebitNote).order_by(DebitNote.posting_date.desc())
    count_query = select(func.count()).select_from(DebitNote)
    total = db.scalar(count_query) or 0

    offset = (page - 1) * per_page
    notes = db.execute(query.offset(offset).limit(per_page)).scalars().all()

    # Stats
    total_amount = db.execute(
        select(func.sum(DebitNote.total_amount))
    ).scalar() or Decimal("0")

    outstanding = db.execute(
        select(func.sum(DebitNote.outstanding_amount)).where(
            DebitNote.outstanding_amount > 0
        )
    ).scalar() or Decimal("0")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Debit Notes"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Debit Notes"},
    ])

    context["notes"] = notes
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page

    context["stats"] = {
        "total_notes": total,
        "total_amount": total_amount,
        "outstanding": outstanding,
    }

    template = templates.get_template("modules/purchasing/templates/pages/debit_notes.html")
    return HTMLResponse(template.render(context))


# ============= PAYMENTS =============

@router.get("/payments", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def purchasing_payments(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Purchase Payments list - payments made to suppliers."""
    from app.models.supplier_payment import SupplierPayment

    today = date.today()
    start_of_month = today.replace(day=1)

    # Query payments where payment_type is "Pay"
    query = select(SupplierPayment).order_by(SupplierPayment.posting_date.desc())

    count_query = select(func.count()).select_from(SupplierPayment)
    total = db.scalar(count_query) or 0

    offset = (page - 1) * per_page
    payments = db.execute(query.offset(offset).limit(per_page)).scalars().all()

    # Stats
    mtd_paid = db.execute(
        select(func.sum(SupplierPayment.paid_amount)).where(
            SupplierPayment.posting_date >= start_of_month
        )
    ).scalar() or Decimal("0")

    total_paid = db.execute(
        select(func.sum(SupplierPayment.paid_amount))
    ).scalar() or Decimal("0")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Purchase Payments"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Payments"},
    ])

    context["payments"] = payments
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page

    context["stats"] = {
        "mtd_paid": mtd_paid,
        "total_paid": total_paid,
        "total_count": total,
    }

    template = templates.get_template("modules/purchasing/templates/pages/payments.html")
    return HTMLResponse(template.render(context))


# ============= ANALYTICS =============

@router.get("/analytics", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def purchasing_analytics(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Purchasing analytics - spend analysis and trends."""
    from sqlalchemy import extract

    today = date.today()
    start_of_year = today.replace(month=1, day=1)
    twelve_months_ago = today - timedelta(days=365)

    # Monthly spend trend
    monthly_spend = db.execute(
        select(
            extract('year', PurchaseInvoice.posting_date).label('year'),
            extract('month', PurchaseInvoice.posting_date).label('month'),
            func.sum(PurchaseInvoice.grand_total).label('total'),
            func.count(PurchaseInvoice.id).label('count'),
        ).where(
            PurchaseInvoice.posting_date >= twelve_months_ago
        ).group_by(
            extract('year', PurchaseInvoice.posting_date),
            extract('month', PurchaseInvoice.posting_date)
        ).order_by(
            extract('year', PurchaseInvoice.posting_date),
            extract('month', PurchaseInvoice.posting_date)
        )
    ).all()

    # Top suppliers by spend YTD
    top_suppliers = db.execute(
        select(
            PurchaseInvoice.supplier_name,
            func.sum(PurchaseInvoice.grand_total).label('total'),
            func.count(PurchaseInvoice.id).label('bill_count'),
        ).where(
            PurchaseInvoice.posting_date >= start_of_year
        ).group_by(
            PurchaseInvoice.supplier_name
        ).order_by(
            func.sum(PurchaseInvoice.grand_total).desc()
        ).limit(10)
    ).all()

    # YTD totals
    ytd_total = db.execute(
        select(func.sum(PurchaseInvoice.grand_total)).where(
            PurchaseInvoice.posting_date >= start_of_year
        )
    ).scalar() or Decimal("0")

    ytd_count = db.execute(
        select(func.count(PurchaseInvoice.id)).where(
            PurchaseInvoice.posting_date >= start_of_year
        )
    ).scalar() or 0

    # Active supplier count
    active_suppliers = db.execute(
        select(func.count(func.distinct(PurchaseInvoice.supplier_name))).where(
            PurchaseInvoice.posting_date >= start_of_year
        )
    ).scalar() or 0

    # Outstanding AP
    total_outstanding = db.execute(
        select(func.sum(PurchaseInvoice.outstanding_amount)).where(
            PurchaseInvoice.outstanding_amount > 0
        )
    ).scalar() or Decimal("0")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Purchasing Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Analytics"},
    ])

    context["monthly_spend"] = [
        {
            "period": f"{int(row.year)}-{int(row.month):02d}",
            "total": float(row.total or 0),
            "count": row.count,
        }
        for row in monthly_spend
    ]

    context["top_suppliers"] = [
        {
            "name": row.supplier_name or "Unknown",
            "total": float(row.total or 0),
            "bill_count": row.bill_count,
        }
        for row in top_suppliers
    ]

    context["stats"] = {
        "ytd_total": ytd_total,
        "ytd_count": ytd_count,
        "active_suppliers": active_suppliers,
        "total_outstanding": total_outstanding,
        "avg_bill": round(float(ytd_total / ytd_count), 2) if ytd_count > 0 else 0,
    }

    template = templates.get_template("modules/purchasing/templates/pages/analytics.html")
    return HTMLResponse(template.render(context))
