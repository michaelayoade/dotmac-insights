"""
Purchasing module web routes.

Provides SSR pages for purchase orders and procurement.
Routes are thin wrappers that delegate to services.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, Depends, Query
from fastapi.responses import HTMLResponse
from typing import Optional
from datetime import date
from decimal import Decimal

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import get_base_context, get_navigation_context, build_breadcrumbs
from app.templates.environment import get_template_env
from app.models.purchasing_order import PurchaseOrderStatus
from app.models.accounting import PurchaseInvoiceStatus

from app.services.purchasing import (
    PurchasingDashboardService,
    BillService,
    APAgingService,
    PurchasingAnalyticsService,
    BillFilters,
)
from app.services.types import PaginationParams
from app.services.purchasing.web_queries import PurchasingQueryService

router = APIRouter(prefix="/purchasing", tags=["purchasing-web"])
templates = get_template_env()

RequirePurchasingRead = Depends(require_scope("purchasing:read"))
RequirePurchasingWrite = Depends(require_scope("purchasing:write"))


# --- Service Providers ---

def get_dashboard_service(db: DB) -> PurchasingDashboardService:
    return PurchasingDashboardService(db)


def get_bill_service(db: DB) -> BillService:
    return BillService(db)


def get_aging_service(db: DB) -> APAgingService:
    return APAgingService(db)


def get_analytics_service(db: DB) -> PurchasingAnalyticsService:
    return PurchasingAnalyticsService(db)


def get_query_service(db: DB) -> PurchasingQueryService:
    return PurchasingQueryService(db)

# Allowed sort columns to prevent SQL injection via getattr
ALLOWED_PO_SORTS = {"transaction_date", "name", "supplier_name", "status", "grand_total"}
ALLOWED_PI_SORTS = {"posting_date", "name", "supplier_name", "status", "grand_total", "due_date"}


@router.get("", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def purchasing_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    dashboard_service: PurchasingDashboardService = Depends(get_dashboard_service),
    bill_service: BillService = Depends(get_bill_service),
    query_service: PurchasingQueryService = Depends(get_query_service),
):
    """Purchasing dashboard - AP overview and key metrics."""
    today = date.today()

    # Get dashboard metrics from service
    metrics = dashboard_service.get_dashboard_metrics(as_of_date=today)

    # Get recent unpaid bills and overdue bills from service
    recent_unpaid_bills = bill_service.get_bills_due_soon(days=365)[:10]
    overdue_bills = bill_service.get_overdue_bills(as_of_date=today)[:10]

    # Calculate overdue count
    overdue_count = len(bill_service.get_overdue_bills(as_of_date=today))

    po_stats = query_service.get_purchase_order_stats()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Purchasing Dashboard"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Dashboard"},
    ])

    context["stats"] = {
        "total_outstanding": metrics.total_outstanding,
        "total_overdue": metrics.total_overdue,
        "overdue_count": overdue_count,
        "overdue_percentage": metrics.overdue_percentage,
        "supplier_count": metrics.supplier_count,
        "due_this_week_count": metrics.due_this_week["count"],
        "due_this_week_total": metrics.due_this_week["total"],
    }

    context["status_breakdown"] = metrics.status_breakdown
    context["top_suppliers"] = metrics.top_suppliers
    context["recent_unpaid_bills"] = recent_unpaid_bills
    context["overdue_bills"] = overdue_bills

    context["po_stats"] = po_stats
    context["today"] = today

    template = templates.get_template("modules/purchasing/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("/orders", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def purchase_orders_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    supplier: Optional[str] = Query(None, description="Filter by supplier"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("transaction_date", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
    query_service: PurchasingQueryService = Depends(get_query_service),
):
    """Purchase orders list page."""
    orders, total = query_service.list_purchase_orders(
        q=q,
        status=status,
        supplier=supplier,
        page=page,
        per_page=per_page,
        sort=sort,
        direction=dir,
        allowed_sorts=ALLOWED_PO_SORTS,
    )

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
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    supplier: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("transaction_date"),
    dir: str = Query("desc"),
    query_service: PurchasingQueryService = Depends(get_query_service),
):
    """Purchase orders table partial for HTMX."""
    # Reuse list logic
    return await purchase_orders_list(
        request, response, user, csrf_token,
        q, status, supplier, page, per_page, sort, dir,
        query_service=query_service,
    )


@router.get("/orders/{order_id}", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def purchase_order_detail(
    order_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    query_service: PurchasingQueryService = Depends(get_query_service),
):
    """Purchase order detail page."""
    order = query_service.get_purchase_order(order_id)

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
    bill_service: BillService = Depends(get_bill_service),
    dashboard_service: PurchasingDashboardService = Depends(get_dashboard_service),
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

    # Validate sort column
    if sort not in ALLOWED_PI_SORTS:
        sort = "posting_date"

    # Build filters for service
    filters = BillFilters(
        status=status.lower() if status else None,
        supplier=supplier or q,  # Use search query for supplier search
        overdue_only=overdue or False,
        sort_by=sort,
        sort_order=dir,
    )

    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    # Get bills from service
    result = bill_service.list_bills(filters, pagination)
    bills = result.data
    total = result.total

    # Get summary stats from dashboard service
    summary = dashboard_service.get_summary_stats()

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
        "total_bills": summary["total_bills"],
        "total_amount": summary["total_outstanding"],
        "outstanding": summary["total_outstanding"],
        "overdue_amount": summary["total_outstanding"],  # Dashboard doesn't break this out
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
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    supplier: Optional[str] = Query(None),
    overdue: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("posting_date"),
    dir: str = Query("desc"),
    bill_service: BillService = Depends(get_bill_service),
    dashboard_service: PurchasingDashboardService = Depends(get_dashboard_service),
):
    """Bills table partial for HTMX."""
    return await bills_list(
        request, response, user, csrf_token, bill_service, dashboard_service,
        q, status, supplier, overdue, page, per_page, sort, dir
    )


@router.get("/bills/{bill_id}", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def bill_detail(
    bill_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    bill_service: BillService = Depends(get_bill_service),
):
    """Bill detail page."""
    from app.services.errors import NotFoundError

    try:
        detail = bill_service.get_bill_detail(bill_id)
    except NotFoundError:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Bill not found"
        return HTMLResponse(template.render(context), status_code=404)

    bill = detail["bill"]
    items = detail["lines"]
    gl_entries = detail["gl_entries"]

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
    aging_service: APAgingService = Depends(get_aging_service),
):
    """AP Aging Report - aged payables by supplier."""
    today = date.today()

    # Get aging report from service
    report = aging_service.get_aging_report(as_of_date=today)
    aging_data = report["aging"]

    # Group by supplier from individual invoices
    supplier_aging: dict = {}
    for bucket_key, bucket_data in aging_data.items():
        for inv in bucket_data["invoices"]:
            supplier = inv["supplier"] or "Unknown"
            if supplier not in supplier_aging:
                supplier_aging[supplier] = {
                    "supplier": supplier,
                    "bill_count": 0,
                    "total": 0.0,
                    "current": 0.0,
                    "days_1_30": 0.0,
                    "days_31_60": 0.0,
                    "days_61_90": 0.0,
                    "over_90": 0.0,
                }
            supplier_aging[supplier]["bill_count"] += 1
            supplier_aging[supplier]["total"] += inv["outstanding"]
            if bucket_key == "current":
                supplier_aging[supplier]["current"] += inv["outstanding"]
            elif bucket_key == "1_30":
                supplier_aging[supplier]["days_1_30"] += inv["outstanding"]
            elif bucket_key == "31_60":
                supplier_aging[supplier]["days_31_60"] += inv["outstanding"]
            elif bucket_key == "61_90":
                supplier_aging[supplier]["days_61_90"] += inv["outstanding"]
            elif bucket_key == "over_90":
                supplier_aging[supplier]["over_90"] += inv["outstanding"]

    # Sort by total descending
    aging_list = sorted(supplier_aging.values(), key=lambda x: x["total"], reverse=True)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "AP Aging Report"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Aging Report"},
    ])

    context["aging_data"] = aging_list

    context["summary"] = {
        "total_bills": report["total_invoices"],
        "total": report["total_payable"],
        "current": aging_data["current"]["total"],
        "days_1_30": aging_data["1_30"]["total"],
        "days_31_60": aging_data["31_60"]["total"],
        "days_61_90": aging_data["61_90"]["total"],
        "over_90": aging_data["over_90"]["total"],
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
    query_service: PurchasingQueryService = Depends(get_query_service),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Expenses list - categorized purchasing expenses."""
    results = query_service.list_expenses(page=page, per_page=per_page)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Expenses"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Expenses"},
    ])

    context["expenses"] = results["expenses"]
    context["total"] = results["total"]
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (results["total"] + per_page - 1) // per_page

    context["stats"] = {
        "mtd_total": results["mtd_total"],
        "ytd_total": results["ytd_total"],
        "total_expenses": results["total"],
    }

    context["by_category"] = results["by_category"]

    template = templates.get_template("modules/purchasing/templates/pages/expenses.html")
    return HTMLResponse(template.render(context))


# ============= DEBIT NOTES =============

@router.get("/debit-notes", response_class=HTMLResponse, dependencies=[RequirePurchasingRead])
async def debit_notes_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    query_service: PurchasingQueryService = Depends(get_query_service),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Debit Notes list - supplier returns and adjustments."""
    results = query_service.list_debit_notes(page=page, per_page=per_page)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Debit Notes"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Debit Notes"},
    ])

    context["notes"] = results["notes"]
    context["total"] = results["total"]
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (results["total"] + per_page - 1) // per_page

    context["stats"] = {
        "total_notes": results["total"],
        "total_amount": results["total_amount"],
        "outstanding": results["outstanding"],
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
    query_service: PurchasingQueryService = Depends(get_query_service),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Purchase Payments list - payments made to suppliers."""
    results = query_service.list_supplier_payments(page=page, per_page=per_page)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Purchase Payments"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Payments"},
    ])

    context["payments"] = results["payments"]
    context["total"] = results["total"]
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (results["total"] + per_page - 1) // per_page

    context["stats"] = {
        "mtd_paid": results["mtd_paid"],
        "total_paid": results["total_paid"],
        "total_count": results["total"],
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
    analytics_service: PurchasingAnalyticsService = Depends(get_analytics_service),
    dashboard_service: PurchasingDashboardService = Depends(get_dashboard_service),
):
    """Purchasing analytics - spend analysis and trends."""
    from datetime import timedelta

    today = date.today()
    start_of_year = today.replace(month=1, day=1)
    twelve_months_ago = today - timedelta(days=365)

    # Get expense trend from service
    trend_data = analytics_service.get_expense_trend(
        start_date=twelve_months_ago,
        end_date=today,
        granularity="month",
    )

    # Get top suppliers from service
    suppliers_data = analytics_service.get_purchases_by_supplier(
        start_date=start_of_year,
        end_date=today,
        limit=10,
    )

    # Get dashboard metrics for summary stats
    metrics = dashboard_service.get_dashboard_metrics(as_of_date=today)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Purchasing Analytics"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Purchasing", "href": "/purchasing"},
        {"label": "Analytics"},
    ])

    context["monthly_spend"] = [
        {
            "period": t["period"],
            "total": t["total"],
            "count": t["entry_count"],
        }
        for t in trend_data["trend"]
    ]

    context["top_suppliers"] = [
        {
            "name": s["name"] or "Unknown",
            "total": s["total_purchases"],
            "bill_count": s["bill_count"],
        }
        for s in suppliers_data["suppliers"]
    ]

    ytd_total = suppliers_data["total"]
    ytd_count = sum(s["bill_count"] for s in suppliers_data["suppliers"])
    active_suppliers = len(suppliers_data["suppliers"])

    context["stats"] = {
        "ytd_total": Decimal(str(ytd_total)),
        "ytd_count": ytd_count,
        "active_suppliers": active_suppliers,
        "total_outstanding": metrics.total_outstanding,
        "avg_bill": round(ytd_total / ytd_count, 2) if ytd_count > 0 else 0,
    }

    template = templates.get_template("modules/purchasing/templates/pages/analytics.html")
    return HTMLResponse(template.render(context))
