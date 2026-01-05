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

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.sales import QuotationStatus, SalesOrderStatus
from app.core.security import is_htmx_request, set_flash, validate_csrf
from app.services.sales import QuotationService, SalesOrderService
from app.services.sales.quotation_types import QuotationFilters, QuotationCreateData, QuotationUpdateData
from app.services.sales.order_types import (
    SalesOrderFilters,
    SalesOrderCreateData,
    SalesOrderUpdateData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError
from app.utils.company_context import get_company_context

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


def _form_str(form: dict, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if value is None:
        return default
    return str(value).strip()

def _form_date(value: str) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


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


@router.get("/quotations/new", response_class=HTMLResponse, dependencies=[RequireSalesWrite])
async def quotation_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New quotation form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Quotation"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Sales"},
        {"label": "Quotations", "href": "/sales/quotations"},
        {"label": "New"},
    ])
    context["is_edit"] = False
    context["form_data"] = {
        "quotation_to": "Customer",
        "party_name": "",
        "customer_name": "",
        "company": "",
        "currency": "NGN",
        "transaction_date": "",
        "valid_till": "",
        "order_type": "",
        "source": "",
        "campaign": "",
    }
    context["errors"] = {}

    template = templates.get_template("modules/sales/templates/quotations/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/quotations", response_class=HTMLResponse, dependencies=[RequireSalesWrite])
async def quotation_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Create a new quotation."""
    await validate_csrf(request)
    form = await request.form()

    quotation_to = _form_str(form, "quotation_to", "Customer")
    party_name = _form_str(form, "party_name")
    customer_name = _form_str(form, "customer_name")
    company = _form_str(form, "company") or get_company_context(allow_null=True)
    currency = _form_str(form, "currency", "NGN") or "NGN"
    transaction_date = _form_date(_form_str(form, "transaction_date"))
    valid_till = _form_date(_form_str(form, "valid_till"))
    order_type = _form_str(form, "order_type")
    source = _form_str(form, "source")
    campaign = _form_str(form, "campaign")

    errors: dict[str, str] = {}
    if not party_name:
        errors["party_name"] = "Customer or lead name is required"
    if not company:
        errors["general"] = "Company is required to create a quotation."

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Quotation"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Sales"},
            {"label": "Quotations", "href": "/sales/quotations"},
            {"label": "New"},
        ])
        context["is_edit"] = False
        context["form_data"] = {
            "quotation_to": quotation_to,
            "party_name": party_name,
            "customer_name": customer_name,
            "company": company or "",
            "currency": currency,
            "transaction_date": _form_str(form, "transaction_date"),
            "valid_till": _form_str(form, "valid_till"),
            "order_type": order_type,
            "source": source,
            "campaign": campaign,
        }
        context["errors"] = errors
        template = templates.get_template("modules/sales/templates/quotations/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    data = QuotationCreateData(
        party_name=party_name,
        quotation_to=quotation_to,
        customer_name=customer_name or None,
        company=company,
        currency=currency,
        transaction_date=transaction_date,
        valid_till=valid_till,
        order_type=order_type or None,
        source=source or None,
        campaign=campaign or None,
    )

    service = QuotationService(db)
    try:
        quote = service.create_quotation(data)
        db.commit()
        db.refresh(quote)
        redirect = RedirectResponse(url=f"/sales/quotations/{quote.id}", status_code=303)
        set_flash(redirect, "Quotation created.", "success")
        return redirect
    except ValidationError as exc:
        redirect = RedirectResponse(url="/sales/quotations/new", status_code=303)
        set_flash(redirect, str(exc), "warning")
        return redirect

@router.get("/quotations/{quotation_id:int}", response_class=HTMLResponse, dependencies=[RequireSalesRead])
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


@router.get("/quotations/{quotation_id:int}/edit", response_class=HTMLResponse, dependencies=[RequireSalesWrite])
async def quotation_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    quotation_id: int,
):
    """Quotation edit form."""
    service = QuotationService(db)
    try:
        quotation = service.get_quotation(quotation_id, include_items=False)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Quotation not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Edit Quotation"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Sales"},
        {"label": "Quotations", "href": "/sales/quotations"},
        {"label": quotation.erpnext_id or f"QTN-{quotation.id}", "href": f"/sales/quotations/{quotation.id}"},
        {"label": "Edit"},
    ])
    context["is_edit"] = True
    context["quotation_id"] = quotation.id
    context["form_data"] = {
        "quotation_to": quotation.quotation_to or "Customer",
        "party_name": quotation.party_name or "",
        "customer_name": quotation.customer_name or "",
        "company": quotation.company or "",
        "currency": quotation.currency or "NGN",
        "transaction_date": quotation.transaction_date.isoformat() if quotation.transaction_date else "",
        "valid_till": quotation.valid_till.isoformat() if quotation.valid_till else "",
        "order_type": quotation.order_type or "",
        "source": quotation.source or "",
        "campaign": quotation.campaign or "",
    }
    context["errors"] = {}

    template = templates.get_template("modules/sales/templates/quotations/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/quotations/{quotation_id:int}", response_class=HTMLResponse, dependencies=[RequireSalesWrite])
async def quotation_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    quotation_id: int,
):
    """Update a quotation."""
    await validate_csrf(request)
    form = await request.form()

    quotation_to = _form_str(form, "quotation_to", "Customer")
    party_name = _form_str(form, "party_name")
    customer_name = _form_str(form, "customer_name")
    company = _form_str(form, "company") or get_company_context(allow_null=True)
    currency = _form_str(form, "currency", "NGN") or "NGN"
    transaction_date = _form_date(_form_str(form, "transaction_date"))
    valid_till = _form_date(_form_str(form, "valid_till"))
    order_type = _form_str(form, "order_type")
    source = _form_str(form, "source")
    campaign = _form_str(form, "campaign")

    errors: dict[str, str] = {}
    if not party_name:
        errors["party_name"] = "Customer or lead name is required"
    if not company:
        errors["general"] = "Company is required to update a quotation."

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Quotation"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Sales"},
            {"label": "Quotations", "href": "/sales/quotations"},
            {"label": f"QTN-{quotation_id}", "href": f"/sales/quotations/{quotation_id}"},
            {"label": "Edit"},
        ])
        context["is_edit"] = True
        context["quotation_id"] = quotation_id
        context["form_data"] = {
            "quotation_to": quotation_to,
            "party_name": party_name,
            "customer_name": customer_name,
            "company": company or "",
            "currency": currency,
            "transaction_date": _form_str(form, "transaction_date"),
            "valid_till": _form_str(form, "valid_till"),
            "order_type": order_type,
            "source": source,
            "campaign": campaign,
        }
        context["errors"] = errors
        template = templates.get_template("modules/sales/templates/quotations/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    data = QuotationUpdateData(
        quotation_to=quotation_to,
        party_name=party_name,
        customer_name=customer_name or None,
        company=company,
        currency=currency,
        transaction_date=transaction_date,
        valid_till=valid_till,
        order_type=order_type or None,
        source=source or None,
        campaign=campaign or None,
    )

    service = QuotationService(db)
    try:
        quote = service.update_quotation(quotation_id, data)
        db.commit()
        db.refresh(quote)
        redirect = RedirectResponse(url=f"/sales/quotations/{quote.id}", status_code=303)
        set_flash(redirect, "Quotation updated.", "success")
        return redirect
    except (NotFoundError, ValidationError) as exc:
        redirect = RedirectResponse(url=f"/sales/quotations/{quotation_id}/edit", status_code=303)
        set_flash(redirect, str(exc), "warning")
        return redirect


@router.post("/quotations/{quotation_id:int}/delete", response_class=HTMLResponse, dependencies=[RequireSalesWrite])
async def quotation_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    quotation_id: int,
):
    """Delete a quotation."""
    await validate_csrf(request)
    service = QuotationService(db)
    try:
        service.delete_quotation(quotation_id)
        db.commit()
        redirect = RedirectResponse(url="/sales/quotations", status_code=303)
        set_flash(redirect, "Quotation deleted.", "success")
        return redirect
    except (NotFoundError, ValidationError) as exc:
        redirect = RedirectResponse(url=f"/sales/quotations/{quotation_id}", status_code=303)
        set_flash(redirect, str(exc), "warning")
        return redirect


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


@router.get("/orders/new", response_class=HTMLResponse, dependencies=[RequireSalesWrite])
async def order_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New sales order form."""

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Sales Order"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Sales"},
        {"label": "Orders", "href": "/sales/orders"},
        {"label": "New"},
    ])

    context["form_data"] = {
        "customer": "",
        "customer_name": "",
        "company": "",
        "currency": "NGN",
        "transaction_date": "",
        "delivery_date": "",
        "order_type": "",
        "source": "",
        "campaign": "",
    }
    context["errors"] = {}

    template = templates.get_template("modules/sales/templates/orders/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/orders", response_class=HTMLResponse, dependencies=[RequireSalesWrite])
async def order_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Create a new sales order."""
    await validate_csrf(request)
    form = await request.form()

    customer = _form_str(form, "customer")
    customer_name = _form_str(form, "customer_name")
    company = _form_str(form, "company") or get_company_context(allow_null=True)
    currency = _form_str(form, "currency", "NGN") or "NGN"
    transaction_date = _form_date(_form_str(form, "transaction_date"))
    delivery_date = _form_date(_form_str(form, "delivery_date"))
    order_type = _form_str(form, "order_type")
    source = _form_str(form, "source")
    campaign = _form_str(form, "campaign")

    errors: dict[str, str] = {}
    if not customer:
        errors["customer"] = "Customer is required"
    if not company:
        errors["general"] = "Company is required to create a sales order."

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Sales Order"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Sales"},
            {"label": "Orders", "href": "/sales/orders"},
            {"label": "New"},
        ])
        context["form_data"] = {
            "customer": customer,
            "customer_name": customer_name,
            "company": company,
            "currency": currency,
            "transaction_date": _form_str(form, "transaction_date"),
            "delivery_date": _form_str(form, "delivery_date"),
            "order_type": order_type,
            "source": source,
            "campaign": campaign,
        }
        context["errors"] = errors
        template = templates.get_template("modules/sales/templates/orders/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    data = SalesOrderCreateData(
        customer=customer,
        customer_name=customer_name or None,
        company=company or None,
        currency=currency,
        transaction_date=transaction_date,
        delivery_date=delivery_date,
        order_type=order_type or None,
        source=source or None,
        campaign=campaign or None,
    )

    service = SalesOrderService(db)
    try:
        order = service.create_order(data)
        db.commit()
        db.refresh(order)
        redirect = RedirectResponse(url=f"/sales/orders/{order.id}", status_code=303)
        set_flash(redirect, "Sales order created.", "success")
        return redirect
    except ValidationError as exc:
        redirect = RedirectResponse(url="/sales/orders/new", status_code=303)
        set_flash(redirect, str(exc), "warning")
        return redirect


@router.get("/orders/{order_id}/edit", response_class=HTMLResponse, dependencies=[RequireSalesWrite])
async def order_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    order_id: int,
):
    """Edit sales order form."""
    service = SalesOrderService(db)
    try:
        order = service.get_order(order_id, include_items=False)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Sales order not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Edit Sales Order"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Sales"},
        {"label": "Orders", "href": "/sales/orders"},
        {"label": order.erpnext_id or f"SO-{order.id}"},
        {"label": "Edit"},
    ])
    context["form_data"] = {
        "customer": order.customer or "",
        "customer_name": order.customer_name or "",
        "company": order.company or "",
        "currency": order.currency or "NGN",
        "transaction_date": order.transaction_date.isoformat() if order.transaction_date else "",
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else "",
        "order_type": order.order_type or "",
        "source": order.source or "",
        "campaign": order.campaign or "",
    }
    context["errors"] = {}
    context["order"] = order

    template = templates.get_template("modules/sales/templates/orders/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/orders/{order_id}", response_class=HTMLResponse, dependencies=[RequireSalesWrite])
async def order_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    order_id: int,
):
    """Update a sales order."""
    await validate_csrf(request)
    form = await request.form()

    customer_name = _form_str(form, "customer_name")
    delivery_date = _form_date(_form_str(form, "delivery_date"))
    order_type = _form_str(form, "order_type")
    source = _form_str(form, "source")
    campaign = _form_str(form, "campaign")

    data = SalesOrderUpdateData(
        customer_name=customer_name or None,
        delivery_date=delivery_date,
        order_type=order_type or None,
        source=source or None,
        campaign=campaign or None,
    )

    service = SalesOrderService(db)
    try:
        service.update_order(order_id, data)
        db.commit()
        redirect = RedirectResponse(url=f"/sales/orders/{order_id}", status_code=303)
        set_flash(redirect, "Sales order updated.", "success")
        return redirect
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        try:
            order = service.get_order(order_id, include_items=False)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Sales order not found") from exc

        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Sales Order"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Sales"},
            {"label": "Orders", "href": "/sales/orders"},
            {"label": order.erpnext_id or f"SO-{order.id}"},
            {"label": "Edit"},
        ])
        context["form_data"] = {
            "customer": order.customer or "",
            "customer_name": customer_name,
            "company": order.company or "",
            "currency": order.currency or "NGN",
            "transaction_date": order.transaction_date.isoformat() if order.transaction_date else "",
            "delivery_date": _form_str(form, "delivery_date"),
            "order_type": order_type,
            "source": source,
            "campaign": campaign,
        }
        context["errors"] = {"general": str(exc)}
        context["order"] = order

        template = templates.get_template("modules/sales/templates/orders/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)


@router.post("/orders/{order_id}/delete", response_class=HTMLResponse, dependencies=[RequireSalesWrite])
async def order_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    order_id: int,
):
    """Delete a sales order."""
    await validate_csrf(request)
    service = SalesOrderService(db)
    try:
        service.delete_order(order_id)
        db.commit()
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    redirect = RedirectResponse(url="/sales/orders", status_code=303)
    set_flash(redirect, "Sales order deleted.", "success")
    return redirect




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
