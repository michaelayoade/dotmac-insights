"""
Sales Module - Quotations, Orders, Invoices & Subscriptions.

Routes:
- /sales - Dashboard (landing page)
- /sales/quotations - Quotations management
- /sales/orders - Sales orders
- /sales/agents - Sales agents leaderboard
- /sales/invoices - Redirects to /invoices
- /sales/subscriptions - Redirects to /subscriptions
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Request, Response, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, DB
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.web.module_types import ModuleConfig
from app.core.security import is_htmx_request

from app.services.sales.dashboard import SalesDashboardService
from app.services.sales.dashboard_types import SalesDashboardFilters

from .routes import router as sales_routes_router

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="sales",
    name="Sales",
    description="Manage quotations, orders, invoices, and subscriptions",
    icon="shopping-cart",
    prefix="/sales",
    group="Back Office",
    order=10,
    scopes=["sales:read"],
    enabled=False,
    prefixes=["/sales", "/invoices", "/subscriptions"],  # All related prefixes
)

NAVIGATION = [
    {
        "section": "Sales",
        "href": "/sales",
        "icon": "shopping-cart",
        "scope": "sales:read",
        "order": 10,
        "links": [
            {"label": "Dashboard", "href": "/sales", "icon": "home"},
            {"label": "Quotations", "href": "/sales/quotations", "icon": "file-text"},
            {"label": "Orders", "href": "/sales/orders", "icon": "shopping-bag"},
            {"label": "Agents", "href": "/sales/agents", "icon": "users"},
        ],
    },
    {
        "section": "Billing",
        "href": "/invoices",
        "icon": "credit-card",
        "scope": "sales:read",
        "order": 20,
        "links": [
            {"label": "Invoices", "href": "/invoices", "icon": "credit-card"},
            {"label": "Subscriptions", "href": "/subscriptions", "icon": "repeat"},
        ],
    },
]

# =============================================================================
# Router
# =============================================================================

templates = get_template_env()

# Main sales router
router = APIRouter(tags=["sales"])


# Period filter options
PERIOD_OPTIONS = [
    {"value": "day", "label": "Today"},
    {"value": "week", "label": "This Week"},
    {"value": "month", "label": "This Month"},
    {"value": "quarter", "label": "This Quarter"},
    {"value": "year", "label": "This Year"},
]


@router.get("/sales", response_class=HTMLResponse)
async def sales_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    period: str = Query("month", description="Time period filter"),
):
    """Sales dashboard - landing page for Sales module."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Sales Dashboard"
    context["now"] = datetime.utcnow()

    # Period filter
    context["period"] = period
    context["period_options"] = PERIOD_OPTIONS

    # Create filters for the dashboard service
    filters = SalesDashboardFilters(period=period)
    dashboard_service = SalesDashboardService(db)

    # Get comprehensive dashboard summary
    summary = dashboard_service.get_dashboard_summary(filters)

    # Build stats from KPI cards
    icon_map = {
        "open_quotes": ("file-text", "bg-blue-50", "text-blue-600", "/sales/quotations?status=open"),
        "quote_value": ("currency-dollar", "bg-indigo-50", "text-indigo-600", "/sales/quotations"),
        "pending_orders": ("shopping-cart", "bg-amber-50", "text-amber-600", "/sales/orders"),
        "order_value": ("shopping-bag", "bg-orange-50", "text-orange-600", "/sales/orders"),
        "revenue": ("trending-up", "bg-green-50", "text-green-600", "/invoices"),
        "fulfillment": ("check-circle", "bg-emerald-50", "text-emerald-600", "/sales/orders?status=completed"),
    }

    stats = []
    for kpi in summary.kpi_cards:
        icon_info = icon_map.get(kpi.key, ("chart-bar", "bg-gray-50", "text-gray-600", "/sales"))
        stats.append({
            "key": kpi.key,
            "label": kpi.title,
            "value": kpi.formatted_value,
            "subtext": kpi.comparison_period or "",
            "icon": icon_info[0],
            "icon_bg": icon_info[1],
            "icon_color": icon_info[2],
            "href": icon_info[3],
            "trend": kpi.trend,
            "trend_direction": kpi.trend_direction,
        })
    context["stats"] = stats

    # Get monthly comparison
    try:
        monthly_comparison = dashboard_service.get_monthly_comparison()
        context["monthly_comparison"] = {
            "current_month": monthly_comparison.current_month,
            "current_orders": monthly_comparison.current_orders,
            "current_revenue": f"₦{monthly_comparison.current_revenue:,.0f}",
            "previous_month": monthly_comparison.previous_month,
            "previous_orders": monthly_comparison.previous_orders,
            "previous_revenue": f"₦{monthly_comparison.previous_revenue:,.0f}",
            "order_change": monthly_comparison.order_change,
            "order_change_percent": monthly_comparison.order_change_percent,
            "revenue_change": monthly_comparison.revenue_change,
            "revenue_change_percent": monthly_comparison.revenue_change_percent,
        }
    except Exception:
        context["monthly_comparison"] = None

    # Get top products
    try:
        top_products = dashboard_service.get_revenue_by_product(limit=5)
        context["top_products"] = [
            {
                "rank": p.rank,
                "name": p.item_name or p.item_code,
                "quantity": p.quantity_sold,
                "revenue": f"₦{p.revenue:,.0f}",
                "orders": p.order_count,
            }
            for p in top_products
        ]
    except Exception:
        context["top_products"] = []

    # Get top customers
    try:
        top_customers = dashboard_service.get_revenue_by_customer(limit=5)
        context["top_customers"] = [
            {
                "rank": c.rank,
                "name": c.party_name or f"Customer {c.party_id}",
                "orders": c.order_count,
                "revenue": f"₦{c.revenue:,.0f}",
                "avg_order": f"₦{c.avg_order_value:,.0f}",
            }
            for c in top_customers
        ]
    except Exception:
        context["top_customers"] = []

    # Quick links
    context["quick_links"] = [
        {"label": "Quotations", "href": "/sales/quotations", "icon": "file-text", "description": "Create and manage quotes"},
        {"label": "Orders", "href": "/sales/orders", "icon": "shopping-cart", "description": "Sales order processing"},
        {"label": "Sales Agents", "href": "/sales/agents", "icon": "users", "description": "Agent performance"},
        {"label": "Invoices", "href": "/invoices", "icon": "credit-card", "description": "Customer invoices"},
    ]

    template = templates.get_template("modules/sales/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# ============= SALES AGENTS =============

@router.get("/sales/agents", response_class=HTMLResponse)
async def sales_agents(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    period: str = Query("month", description="Time period filter"),
    territory: Optional[str] = Query(None, description="Filter by territory"),
):
    """Sales agents leaderboard - performance by sales person."""
    from sqlalchemy import func
    from app.models.sales import SalesPerson, SalesOrder, Territory

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Sales Agents"
    context["now"] = datetime.utcnow()
    context["period"] = period
    context["period_options"] = PERIOD_OPTIONS
    context["territory_filter"] = territory

    # Get period start date
    today = date.today()
    if period == "day":
        period_start = today
    elif period == "week":
        period_start = today - timedelta(days=today.weekday())
    elif period == "month":
        period_start = date(today.year, today.month, 1)
    elif period == "quarter":
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        period_start = date(today.year, quarter_month, 1)
    else:  # year
        period_start = date(today.year, 1, 1)

    # Get all territories for filter
    territories = db.query(Territory).filter(Territory.is_group == False).order_by(Territory.territory_name).all()
    context["territories"] = [{"value": t.territory_name, "label": t.territory_name} for t in territories]

    # Get sales persons with their order stats
    agents_data = []
    sales_persons = db.query(SalesPerson).filter(SalesPerson.enabled == True).all()

    for sp in sales_persons:
        # Build query for orders by this sales person
        order_query = db.query(SalesOrder).filter(
            SalesOrder.sales_partner_id == sp.id,
            SalesOrder.transaction_date >= period_start,
        )

        # Apply territory filter if specified
        if territory:
            order_query = order_query.filter(SalesOrder.territory == territory)

        orders = order_query.all()
        order_count = len(orders)
        total_revenue = sum(o.grand_total or Decimal("0") for o in orders)
        avg_order_value = total_revenue / order_count if order_count > 0 else Decimal("0")

        # Only include agents with activity
        if order_count > 0:
            agents_data.append({
                "id": sp.id,
                "name": sp.sales_person_name,
                "department": sp.department or "—",
                "orders": order_count,
                "revenue": total_revenue,
                "revenue_formatted": f"₦{total_revenue:,.0f}",
                "avg_order": f"₦{avg_order_value:,.0f}",
                "commission_rate": f"{sp.commission_rate:.1f}%",
            })

    # Sort by revenue descending and assign ranks
    agents_data.sort(key=lambda x: x["revenue"], reverse=True)
    for i, agent in enumerate(agents_data, 1):
        agent["rank"] = i

    context["agents"] = agents_data
    context["total_agents"] = len(agents_data)
    context["total_revenue"] = f"₦{sum(a['revenue'] for a in agents_data):,.0f}"
    context["total_orders"] = sum(a["orders"] for a in agents_data)

    template = templates.get_template("modules/sales/templates/pages/agents.html")
    return HTMLResponse(template.render(context))


# Redirect /sales/invoices to /invoices
@router.get("/sales/invoices")
async def sales_invoices_redirect():
    return RedirectResponse(url="/invoices", status_code=302)


@router.get("/sales/invoices/new")
async def sales_invoices_new_redirect():
    return RedirectResponse(url="/accounting/invoices/new", status_code=302)


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
