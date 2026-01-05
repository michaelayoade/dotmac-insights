"""
Sales Routes - Quotations and Sales Orders with SSR + HTMX.

Permission Requirements:
- sales:read - View quotations and orders
- sales:write - Create, update quotations and orders

Routes are thin wrappers around services - all business logic is in:
- QuotationService: app/services/sales/quotations.py
- SalesOrderService: app/services/sales/orders.py
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.sales import QuotationStatus, SalesOrderStatus
from app.core.security import is_htmx_request
from app.services.sales import QuotationService, SalesOrderService
from app.services.sales.quotation_types import QuotationFilters
from app.services.sales.order_types import SalesOrderFilters
from app.services.types import PaginationParams
from app.services.errors import NotFoundError

# Permission dependencies
RequireSalesRead = Depends(require_scope("sales:read"))
RequireSalesWrite = Depends(require_scope("sales:write"))

router = APIRouter(prefix="/sales", tags=["sales"])
templates = get_template_env()


# ============= QUOTATIONS =============

def get_quotation_status_options():
    """Get quotation status options for filter dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in QuotationStatus
    ]


@router.get("/quotations", response_class=HTMLResponse, dependencies=[RequireSalesRead])
async def quotations_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Quotations list page."""
    # Use service for all data access
    service = QuotationService(db)

    # Build filters
    filters = QuotationFilters(search=q, status=status) if q or status else None

    # Get paginated quotations
    offset = (page - 1) * per_page
    pagination_params = PaginationParams(offset=offset, limit=per_page)
    result = service.list_quotations(filters=filters, pagination=pagination_params)

    # Get summary stats from service
    summary = service.get_summary()

    # Map summary to template-friendly stats dict
    stats = {
        "total_count": summary.total_count,
        "total_value": summary.total_value,
        "open_count": summary.open_count,
        "ordered_count": summary.ordered_count,
        "lost_count": summary.lost_count,
    }

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["quotations"] = result.items
    context["search_query"] = q or ""
    context["current_status"] = status
    context["status_options"] = get_quotation_status_options()
    context["stats"] = stats
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/sales/templates/quotations/partials/quotations_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Quotations"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Sales"},
        {"label": "Quotations"},
    ])

    template = templates.get_template("modules/sales/templates/quotations/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/quotations/table", response_class=HTMLResponse, dependencies=[RequireSalesRead])
async def quotations_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Quotations table partial for HTMX updates."""
    return await quotations_list(
        request, response, user, csrf_token, db,
        q, status, page, per_page
    )


@router.get("/quotations/{quotation_id}", response_class=HTMLResponse, dependencies=[RequireSalesRead])
async def quotation_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    quotation_id: int,
):
    """Quotation detail page."""
    service = QuotationService(db)

    try:
        quotation = service.get_quotation(quotation_id, include_items=True)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Quotation not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = quotation.erpnext_id or f"QTN-{quotation.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Sales"},
        {"label": "Quotations", "href": "/sales/quotations"},
        {"label": quotation.erpnext_id or f"QTN-{quotation.id}"},
    ])
    context["quotation"] = quotation

    template = templates.get_template("modules/sales/templates/quotations/pages/detail.html")
    return HTMLResponse(template.render(context))


# ============= SALES ORDERS =============

def get_order_status_options():
    """Get order status options for filter dropdown."""
    labels = {
        "draft": "Draft",
        "to_deliver_and_bill": "To Deliver & Bill",
        "to_bill": "To Bill",
        "to_deliver": "To Deliver",
        "completed": "Completed",
        "cancelled": "Cancelled",
        "closed": "Closed",
        "on_hold": "On Hold",
    }
    return [
        {"value": s.value, "label": labels.get(s.value, s.value.replace("_", " ").title())}
        for s in SalesOrderStatus
    ]


@router.get("/orders", response_class=HTMLResponse, dependencies=[RequireSalesRead])
async def orders_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Sales orders list page."""
    # Use service for all data access
    service = SalesOrderService(db)

    # Build filters
    filters = SalesOrderFilters(search=q, status=status) if q or status else None

    # Get paginated orders
    offset = (page - 1) * per_page
    pagination_params = PaginationParams(offset=offset, limit=per_page)
    result = service.list_orders(filters=filters, pagination=pagination_params)

    # Get summary stats from service
    summary = service.get_summary()

    # Map summary to template-friendly stats dict
    stats = {
        "total_count": summary.total_count,
        "total_value": summary.total_value,
        "to_deliver_count": summary.pending_delivery_count,
        "to_bill_count": summary.pending_billing_count,
        "completed_count": summary.completed_count,
    }

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["orders"] = result.items
    context["search_query"] = q or ""
    context["current_status"] = status
    context["status_options"] = get_order_status_options()
    context["stats"] = stats
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/sales/templates/orders/partials/orders_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Sales Orders"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Sales"},
        {"label": "Orders"},
    ])

    template = templates.get_template("modules/sales/templates/orders/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/orders/table", response_class=HTMLResponse, dependencies=[RequireSalesRead])
async def orders_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Sales orders table partial for HTMX updates."""
    return await orders_list(
        request, response, user, csrf_token, db,
        q, status, page, per_page
    )


@router.get("/orders/{order_id}", response_class=HTMLResponse, dependencies=[RequireSalesRead])
async def order_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    order_id: int,
):
    """Sales order detail page."""
    service = SalesOrderService(db)

    try:
        order = service.get_order(order_id, include_items=True)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Sales order not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = order.erpnext_id or f"SO-{order.id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Sales"},
        {"label": "Orders", "href": "/sales/orders"},
        {"label": order.erpnext_id or f"SO-{order.id}"},
    ])
    context["order"] = order

    template = templates.get_template("modules/sales/templates/orders/pages/detail.html")
    return HTMLResponse(template.render(context))
