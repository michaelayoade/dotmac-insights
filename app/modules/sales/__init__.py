"""
Sales Module - Quotations, Orders, Invoices & Subscriptions.

Routes:
- /sales - Dashboard (landing page)
- /sales/quotations - Quotations management
- /sales/orders - Sales orders
- /sales/invoices - Redirects to /invoices
- /sales/subscriptions - Redirects to /subscriptions
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func

from app.web.dependencies import SessionUser, CSRFToken, DB
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env

# Import models for dashboard stats
from app.models.sales import Quotation, QuotationStatus, SalesOrder, SalesOrderStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.subscription import Subscription, SubscriptionStatus

from .routes import router as sales_routes_router

templates = get_template_env()

# Main sales router
router = APIRouter(tags=["sales"])


@router.get("/sales", response_class=HTMLResponse)
async def sales_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Sales dashboard - landing page for Sales module."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Sales"
    context["now"] = datetime.utcnow()

    # Gather stats
    stats = []

    # Open Quotations
    open_quotes = db.query(func.count(Quotation.id)).filter(
        Quotation.status == QuotationStatus.OPEN,
        Quotation.is_deleted == False,
    ).scalar() or 0
    stats.append({
        "key": "quotations",
        "label": "Open Quotations",
        "value": f"{open_quotes:,}",
        "subtext": "Pending approval",
        "icon": "file-text",
        "icon_bg": "bg-blue-50",
        "icon_color": "text-blue-600",
        "href": "/sales/quotations",
    })

    # Pending Orders
    pending_orders = db.query(func.count(SalesOrder.id)).filter(
        SalesOrder.status.in_([
            SalesOrderStatus.DRAFT,
            SalesOrderStatus.TO_DELIVER_AND_BILL,
            SalesOrderStatus.TO_BILL,
            SalesOrderStatus.TO_DELIVER,
        ]),
    ).scalar() or 0
    stats.append({
        "key": "orders",
        "label": "Pending Orders",
        "value": f"{pending_orders:,}",
        "subtext": "Awaiting fulfillment",
        "icon": "shopping-cart",
        "icon_bg": "bg-amber-50",
        "icon_color": "text-amber-600",
        "href": "/sales/orders",
    })

    # Pending Invoices
    pending_invoices = db.query(func.count(Invoice.id)).filter(
        Invoice.status.in_([
            InvoiceStatus.PENDING,
            InvoiceStatus.PARTIALLY_PAID,
        ])
    ).scalar() or 0
    stats.append({
        "key": "invoices",
        "label": "Pending Invoices",
        "value": f"{pending_invoices:,}",
        "subtext": "Awaiting payment",
        "icon": "credit-card",
        "icon_bg": "bg-emerald-50",
        "icon_color": "text-emerald-600",
        "href": "/invoices",
    })

    # Active Subscriptions
    active_subs = db.query(func.count(Subscription.id)).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).scalar() or 0
    stats.append({
        "key": "subscriptions",
        "label": "Active Subscriptions",
        "value": f"{active_subs:,}",
        "subtext": "Recurring revenue",
        "icon": "repeat",
        "icon_bg": "bg-purple-50",
        "icon_color": "text-purple-600",
        "href": "/subscriptions",
    })

    # Revenue MTD
    today = date.today()
    month_start = date(today.year, today.month, 1)
    revenue_mtd = db.query(func.sum(Invoice.total_amount)).filter(
        Invoice.invoice_date >= month_start,
        Invoice.status.in_([InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID])
    ).scalar() or Decimal("0")
    stats.append({
        "key": "revenue",
        "label": "Revenue MTD",
        "value": f"${revenue_mtd:,.0f}",
        "subtext": "This month",
        "icon": "trending-up",
        "icon_bg": "bg-green-50",
        "icon_color": "text-green-600",
        "href": "/invoices",
    })

    context["stats"] = stats

    # Quick links
    context["quick_links"] = [
        {"label": "Quotations", "href": "/sales/quotations", "icon": "file-text", "description": "Create and manage quotes"},
        {"label": "Orders", "href": "/sales/orders", "icon": "shopping-cart", "description": "Sales order processing"},
        {"label": "Invoices", "href": "/invoices", "icon": "credit-card", "description": "Customer invoices"},
        {"label": "Subscriptions", "href": "/subscriptions", "icon": "repeat", "description": "Recurring billing"},
    ]

    template = templates.get_template("modules/sales/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# Redirect /sales/invoices to /invoices
@router.get("/sales/invoices")
async def sales_invoices_redirect():
    return RedirectResponse(url="/invoices", status_code=302)


@router.get("/sales/invoices/{path:path}")
async def sales_invoices_path_redirect(path: str):
    return RedirectResponse(url=f"/invoices/{path}", status_code=302)


# Redirect /sales/subscriptions to /subscriptions
@router.get("/sales/subscriptions")
async def sales_subscriptions_redirect():
    return RedirectResponse(url="/subscriptions", status_code=302)


@router.get("/sales/subscriptions/{path:path}")
async def sales_subscriptions_path_redirect(path: str):
    return RedirectResponse(url=f"/subscriptions/{path}", status_code=302)


# Include the original sales routes (quotations and orders)
router.include_router(sales_routes_router)
