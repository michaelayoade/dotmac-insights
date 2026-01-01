"""
Sales Routes - Quotations and Sales Orders with SSR + HTMX.

Permission Requirements:
- sales:read - View quotations and orders
- sales:write - Create, update quotations and orders
"""
from __future__ import annotations

from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.sales import Quotation, QuotationStatus, SalesOrder, SalesOrderStatus
from app.core.security import is_htmx_request

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


def get_quotation_stats(db) -> dict:
    """Calculate quotation statistics."""
    total_count = db.query(func.count(Quotation.id)).filter(
        Quotation.is_deleted == False
    ).scalar() or 0

    total_value = db.query(func.sum(Quotation.grand_total)).filter(
        Quotation.is_deleted == False
    ).scalar() or Decimal("0")

    open_count = db.query(func.count(Quotation.id)).filter(
        Quotation.is_deleted == False,
        Quotation.status == QuotationStatus.OPEN
    ).scalar() or 0

    ordered_count = db.query(func.count(Quotation.id)).filter(
        Quotation.is_deleted == False,
        Quotation.status == QuotationStatus.ORDERED
    ).scalar() or 0

    lost_count = db.query(func.count(Quotation.id)).filter(
        Quotation.is_deleted == False,
        Quotation.status == QuotationStatus.LOST
    ).scalar() or 0

    return {
        "total_count": total_count,
        "total_value": total_value,
        "open_count": open_count,
        "ordered_count": ordered_count,
        "lost_count": lost_count,
    }


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
    # Build query
    query = db.query(Quotation).filter(Quotation.is_deleted == False)

    # Search
    if q:
        search_filter = or_(
            Quotation.erpnext_id.ilike(f"%{q}%"),
            Quotation.party_name.ilike(f"%{q}%"),
            Quotation.customer_name.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(Quotation.status == status)

    # Count total
    total = query.count()

    # Sort
    query = query.order_by(Quotation.transaction_date.desc().nullsfirst(), Quotation.id.desc())

    # Paginate
    offset = (page - 1) * per_page
    quotations = query.offset(offset).limit(per_page).all()

    # Get stats
    stats = get_quotation_stats(db)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["quotations"] = quotations
    context["search_query"] = q or ""
    context["current_status"] = status
    context["status_options"] = get_quotation_status_options()
    context["stats"] = stats
    context["pagination"] = build_pagination_context(page, per_page, total)

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
    quotation = db.query(Quotation).filter(
        Quotation.id == quotation_id,
        Quotation.is_deleted == False,
    ).first()

    if not quotation:
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


def get_order_stats(db) -> dict:
    """Calculate sales order statistics."""
    total_count = db.query(func.count(SalesOrder.id)).scalar() or 0

    total_value = db.query(func.sum(SalesOrder.grand_total)).scalar() or Decimal("0")

    to_deliver_count = db.query(func.count(SalesOrder.id)).filter(
        SalesOrder.status.in_([
            SalesOrderStatus.TO_DELIVER,
            SalesOrderStatus.TO_DELIVER_AND_BILL
        ])
    ).scalar() or 0

    to_bill_count = db.query(func.count(SalesOrder.id)).filter(
        SalesOrder.status.in_([
            SalesOrderStatus.TO_BILL,
            SalesOrderStatus.TO_DELIVER_AND_BILL
        ])
    ).scalar() or 0

    completed_count = db.query(func.count(SalesOrder.id)).filter(
        SalesOrder.status == SalesOrderStatus.COMPLETED
    ).scalar() or 0

    return {
        "total_count": total_count,
        "total_value": total_value,
        "to_deliver_count": to_deliver_count,
        "to_bill_count": to_bill_count,
        "completed_count": completed_count,
    }


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
    # Build query
    query = db.query(SalesOrder)

    # Search
    if q:
        search_filter = or_(
            SalesOrder.erpnext_id.ilike(f"%{q}%"),
            SalesOrder.customer.ilike(f"%{q}%"),
            SalesOrder.customer_name.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(SalesOrder.status == status)

    # Count total
    total = query.count()

    # Sort
    query = query.order_by(SalesOrder.transaction_date.desc().nullsfirst(), SalesOrder.id.desc())

    # Paginate
    offset = (page - 1) * per_page
    orders = query.offset(offset).limit(per_page).all()

    # Get stats
    stats = get_order_stats(db)

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["orders"] = orders
    context["search_query"] = q or ""
    context["current_status"] = status
    context["status_options"] = get_order_status_options()
    context["stats"] = stats
    context["pagination"] = build_pagination_context(page, per_page, total)

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
    order = db.query(SalesOrder).filter(
        SalesOrder.id == order_id
    ).first()

    if not order:
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
