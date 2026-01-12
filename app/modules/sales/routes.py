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
import logging
from typing import Optional, Callable, TypeVar

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
from decimal import Decimal
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from app.models.sales import QuotationStatus, SalesOrderStatus, SalesPerson, ERPNextLead, Quotation, SalesOrder
from app.models.party import CustomerAccount
from app.models.tax import TaxCode
from app.core.security import is_htmx_request, set_flash, validate_csrf
from app.services.sales import QuotationService, SalesOrderService
from app.services.sales.quotation_types import (
    QuotationFilters,
    QuotationCreateData,
    QuotationUpdateData,
    QuotationLineItemData,
)
from app.services.sales.order_types import (
    SalesOrderFilters,
    SalesOrderCreateData,
    SalesOrderUpdateData,
    SalesOrderLineItemData,
)
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError
from app.utils.company_context import get_company_context

# Permission dependencies
RequireSalesRead = Depends(require_scope("sales:read"))
RequireSalesWrite = Depends(require_scope("sales:write"))

router = APIRouter(prefix="/sales", tags=["sales"])
templates = get_template_env()
logger = logging.getLogger(__name__)

T = TypeVar("T")


def _safe_query_list(fetcher: Callable[[], list[T]], label: str) -> list[T]:
    try:
        return fetcher()
    except SQLAlchemyError as exc:
        logger.warning("sales_form_options_load_failed", extra={"option": label, "error": str(exc)})
        return []


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

def _form_int(form: dict, key: str, default: Optional[int] = None) -> Optional[int]:
    value = form.get(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _form_decimal(form: dict, key: str, default: Decimal = Decimal("0")) -> Decimal:
    value = form.get(key, "")
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return default

def _form_date(value: str) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None

def _extract_party_address(addresses: list[dict]) -> dict:
    if not addresses:
        return {}
    first = addresses[0]
    if not isinstance(first, dict):
        return {}
    return {
        "address_line1": first.get("address_line1") or first.get("line1") or first.get("street_1") or first.get("address"),
        "address_line2": first.get("address_line2") or first.get("line2") or first.get("street_2"),
        "city": first.get("city"),
        "state": first.get("state"),
        "postal_code": first.get("postal_code") or first.get("zip") or first.get("zip_code"),
        "country": first.get("country"),
        "gps_lat": first.get("gps_lat"),
        "gps_lng": first.get("gps_lng"),
    }


def _format_party_address(addresses: list[dict]) -> str:
    address = _extract_party_address(addresses)
    if not address:
        return ""
    parts = [
        address.get("address_line1"),
        address.get("address_line2"),
        address.get("city"),
        address.get("state"),
        address.get("postal_code"),
        address.get("country"),
    ]
    return ", ".join([part for part in parts if part])


def _get_customer_accounts(db: DB) -> list[dict]:
    company = get_company_context(allow_null=True) or ""
    def fetch_accounts() -> list[dict]:
        accounts = (
            db.query(CustomerAccount)
            .options(joinedload(CustomerAccount.party))
            .order_by(CustomerAccount.id.desc())
            .limit(200)
            .all()
        )
        options = []
        for account in accounts:
            party = account.party
            party_name = ""
            contact_email = ""
            contact_phone = ""
            address = ""
            addr_struct = {}
            if party:
                party_name = party.name or party.legal_name or party.trading_name or ""
                contact_email = party.primary_email or ""
                contact_phone = party.primary_phone or ""
                if party.addresses:
                    addr_struct = _extract_party_address(party.addresses)
                    address = _format_party_address(party.addresses)
            options.append(
                {
                    "id": account.id,
                    "name": party_name or f"Account {account.id}",
                    "contact_name": party_name,
                    "contact_email": contact_email,
                    "contact_phone": contact_phone,
                    "billing_address": address,
                    "shipping_address": address,
                    "billing_address_line1": addr_struct.get("address_line1", ""),
                    "billing_address_line2": addr_struct.get("address_line2", ""),
                    "billing_city": addr_struct.get("city", ""),
                    "billing_state": addr_struct.get("state", ""),
                    "billing_postal_code": addr_struct.get("postal_code", ""),
                    "billing_country": addr_struct.get("country", ""),
                    "billing_gps_lat": addr_struct.get("gps_lat", ""),
                    "billing_gps_lng": addr_struct.get("gps_lng", ""),
                    "shipping_address_line1": addr_struct.get("address_line1", ""),
                    "shipping_address_line2": addr_struct.get("address_line2", ""),
                    "shipping_city": addr_struct.get("city", ""),
                    "shipping_state": addr_struct.get("state", ""),
                    "shipping_postal_code": addr_struct.get("postal_code", ""),
                    "shipping_country": addr_struct.get("country", ""),
                    "shipping_gps_lat": addr_struct.get("gps_lat", ""),
                    "shipping_gps_lng": addr_struct.get("gps_lng", ""),
                    "currency": account.currency or "NGN",
                    "company": company,
                }
            )
        return options
    return _safe_query_list(fetch_accounts, "customer_accounts")

def _get_sales_people(db: DB) -> list[SalesPerson]:
    return _safe_query_list(
        lambda: db.query(SalesPerson).filter(SalesPerson.enabled == True).order_by(SalesPerson.sales_person_name).all(),
        "sales_people",
    )

def _get_tax_codes(db: DB) -> list[TaxCode]:
    return _safe_query_list(
        lambda: db.query(TaxCode).filter(TaxCode.is_active == True).order_by(TaxCode.code).all(),
        "tax_codes",
    )

def _get_recent_quotations(db: DB) -> list[dict]:
    def fetch_quotes() -> list[dict]:
        quotes = (
            db.query(Quotation)
            .options(joinedload(Quotation.items))
            .filter(Quotation.is_deleted == False)
            .order_by(Quotation.id.desc())
            .limit(200)
            .all()
        )
        results = []
        for quote in quotes:
            items = []
            for item in quote.items or []:
                items.append(
                    {
                        "name": item.item_name or item.item_code or "Item",
                        "qty": float(item.qty or 0),
                        "rate": float(item.rate or 0),
                        "tax_code_id": item.tax_code_id,
                    }
                )
            results.append(
                {
                    "id": quote.id,
                    "erpnext_id": quote.erpnext_id,
                    "customer_name": quote.customer_name,
                    "party_name": quote.party_name,
                    "customer_account_id": quote.customer_account_id,
                    "contact_name": quote.contact_name,
                    "contact_email": quote.contact_email,
                    "contact_phone": quote.contact_phone,
                    "billing_address": quote.billing_address,
                    "shipping_address": quote.shipping_address,
                    "billing_address_line1": quote.billing_address_line1,
                    "billing_address_line2": quote.billing_address_line2,
                    "billing_city": quote.billing_city,
                    "billing_state": quote.billing_state,
                    "billing_postal_code": quote.billing_postal_code,
                    "billing_country": quote.billing_country,
                    "billing_gps_lat": quote.billing_gps_lat,
                    "billing_gps_lng": quote.billing_gps_lng,
                    "shipping_address_line1": quote.shipping_address_line1,
                    "shipping_address_line2": quote.shipping_address_line2,
                    "shipping_city": quote.shipping_city,
                    "shipping_state": quote.shipping_state,
                    "shipping_postal_code": quote.shipping_postal_code,
                    "shipping_country": quote.shipping_country,
                    "shipping_gps_lat": quote.shipping_gps_lat,
                    "shipping_gps_lng": quote.shipping_gps_lng,
                    "company": quote.company,
                    "currency": quote.currency,
                    "items": items,
                }
            )
        return results
    return _safe_query_list(fetch_quotes, "quotations")

def _get_recent_leads(db: DB) -> list[ERPNextLead]:
    return _safe_query_list(
        lambda: db.query(ERPNextLead).order_by(ERPNextLead.id.desc()).limit(200).all(),
        "leads",
    )

def _parse_line_items(form: dict, tax_codes: dict[int, TaxCode]) -> list[SalesOrderLineItemData]:
    indices = []
    for key in form.keys():
        if key.startswith("line_item_name_"):
            try:
                indices.append(int(key.rsplit("_", 1)[-1]))
            except ValueError:
                continue
    indices = sorted(set(indices))

    items: list[SalesOrderLineItemData] = []
    for idx in indices:
        name = _form_str(form, f"line_item_name_{idx}")
        qty = _form_decimal(form, f"line_item_qty_{idx}", Decimal("1")) or Decimal("1")
        rate = _form_decimal(form, f"line_item_rate_{idx}", Decimal("0")) or Decimal("0")
        tax_code_id = _form_int(form, f"line_item_tax_{idx}")
        if not name and rate == Decimal("0"):
            continue

        tax_rate = Decimal("0")
        if tax_code_id and tax_code_id in tax_codes:
            tax_rate = Decimal(str(tax_codes[tax_code_id].rate or 0))

        items.append(SalesOrderLineItemData(
            item_code=name,
            item_name=name,
            qty=qty,
            rate=rate,
            tax_code_id=tax_code_id,
            tax_rate=tax_rate,
        ))

    return items

def _parse_quote_line_items(form: dict, tax_codes: dict[int, TaxCode]) -> list[QuotationLineItemData]:
    indices = []
    for key in form.keys():
        if key.startswith("line_item_name_"):
            try:
                indices.append(int(key.rsplit("_", 1)[-1]))
            except ValueError:
                continue
    indices = sorted(set(indices))

    items: list[QuotationLineItemData] = []
    for idx in indices:
        name = _form_str(form, f"line_item_name_{idx}")
        qty = _form_decimal(form, f"line_item_qty_{idx}", Decimal("1")) or Decimal("1")
        rate = _form_decimal(form, f"line_item_rate_{idx}", Decimal("0")) or Decimal("0")
        tax_code_id = _form_int(form, f"line_item_tax_{idx}")
        if not name and rate == Decimal("0"):
            continue

        tax_rate = Decimal("0")
        if tax_code_id and tax_code_id in tax_codes:
            tax_rate = Decimal(str(tax_codes[tax_code_id].rate or 0))

        items.append(QuotationLineItemData(
            item_code=name,
            item_name=name,
            qty=qty,
            rate=rate,
            tax_code_id=tax_code_id,
            tax_rate=tax_rate,
        ))

    return items


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
        "customer_name": "",
        "customer_account_id": "",
        "lead_id": "",
        "contact_name": "",
        "contact_email": "",
        "contact_phone": "",
        "billing_address_line1": "",
        "billing_address_line2": "",
        "billing_city": "",
        "billing_state": "",
        "billing_postal_code": "",
        "billing_country": "",
        "billing_gps_lat": "",
        "billing_gps_lng": "",
        "shipping_address_line1": "",
        "shipping_address_line2": "",
        "shipping_city": "",
        "shipping_state": "",
        "shipping_postal_code": "",
        "shipping_country": "",
        "shipping_gps_lat": "",
        "shipping_gps_lng": "",
        "company": "",
        "currency": "NGN",
        "transaction_date": "",
        "valid_till": "",
        "order_type": "",
        "source": "",
        "campaign": "",
        "status": QuotationStatus.DRAFT.value,
        "sales_partner_id": "",
    }
    context["status_options"] = get_quotation_status_options()
    context["customer_accounts"] = _get_customer_accounts(db)
    context["leads"] = _get_recent_leads(db)
    context["sales_people"] = _get_sales_people(db)
    context["tax_codes"] = _get_tax_codes(db)
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
    customer_name = _form_str(form, "customer_name") or _form_str(form, "party_name")
    party_name = customer_name
    customer_account_id = _form_int(form, "customer_account_id")
    lead_id = _form_int(form, "lead_id")
    contact_name = _form_str(form, "contact_name")
    contact_email = _form_str(form, "contact_email")
    contact_phone = _form_str(form, "contact_phone")
    billing_address_line1 = _form_str(form, "billing_address_line1")
    billing_address_line2 = _form_str(form, "billing_address_line2")
    billing_city = _form_str(form, "billing_city")
    billing_state = _form_str(form, "billing_state")
    billing_postal_code = _form_str(form, "billing_postal_code")
    billing_country = _form_str(form, "billing_country")
    billing_gps_lat = _form_decimal(form, "billing_gps_lat")
    billing_gps_lng = _form_decimal(form, "billing_gps_lng")
    shipping_address_line1 = _form_str(form, "shipping_address_line1")
    shipping_address_line2 = _form_str(form, "shipping_address_line2")
    shipping_city = _form_str(form, "shipping_city")
    shipping_state = _form_str(form, "shipping_state")
    shipping_postal_code = _form_str(form, "shipping_postal_code")
    shipping_country = _form_str(form, "shipping_country")
    shipping_gps_lat = _form_decimal(form, "shipping_gps_lat")
    shipping_gps_lng = _form_decimal(form, "shipping_gps_lng")
    company = _form_str(form, "company") or get_company_context(allow_null=True)
    currency = _form_str(form, "currency", "NGN") or "NGN"
    transaction_date = _form_date(_form_str(form, "transaction_date"))
    valid_till = _form_date(_form_str(form, "valid_till"))
    order_type = _form_str(form, "order_type")
    source = _form_str(form, "source")
    campaign = _form_str(form, "campaign")
    status = _form_str(form, "status", QuotationStatus.DRAFT.value)
    sales_partner_id = _form_int(form, "sales_partner_id")

    tax_codes = {tc.id: tc for tc in _get_tax_codes(db)}
    items = _parse_quote_line_items(form, tax_codes)
    if not items:
        items = None

    errors: dict[str, str] = {}
    if not party_name and not customer_account_id and not lead_id:
        errors["customer_name"] = "Customer or lead name is required"
    if not items:
        errors["items"] = "At least one line item is required"
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
            "customer_name": customer_name,
            "customer_account_id": str(customer_account_id) if customer_account_id else "",
            "lead_id": str(lead_id) if lead_id else "",
            "contact_name": contact_name,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "billing_address_line1": billing_address_line1,
            "billing_address_line2": billing_address_line2,
            "billing_city": billing_city,
            "billing_state": billing_state,
            "billing_postal_code": billing_postal_code,
            "billing_country": billing_country,
            "billing_gps_lat": str(billing_gps_lat or ""),
            "billing_gps_lng": str(billing_gps_lng or ""),
            "shipping_address_line1": shipping_address_line1,
            "shipping_address_line2": shipping_address_line2,
            "shipping_city": shipping_city,
            "shipping_state": shipping_state,
            "shipping_postal_code": shipping_postal_code,
            "shipping_country": shipping_country,
            "shipping_gps_lat": str(shipping_gps_lat or ""),
            "shipping_gps_lng": str(shipping_gps_lng or ""),
            "company": company or "",
            "currency": currency,
            "transaction_date": _form_str(form, "transaction_date"),
            "valid_till": _form_str(form, "valid_till"),
            "order_type": order_type,
            "source": source,
            "campaign": campaign,
            "status": status,
            "sales_partner_id": str(sales_partner_id) if sales_partner_id else "",
        }
        context["status_options"] = get_quotation_status_options()
        context["customer_accounts"] = _get_customer_accounts(db)
        context["leads"] = _get_recent_leads(db)
        context["sales_people"] = _get_sales_people(db)
        context["tax_codes"] = list(tax_codes.values())
        context["errors"] = errors
        template = templates.get_template("modules/sales/templates/quotations/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    data = QuotationCreateData(
        party_name=party_name,
        quotation_to=quotation_to,
        customer_name=customer_name or None,
        customer_account_id=customer_account_id,
        lead_id=lead_id,
        contact_name=contact_name or None,
        contact_email=contact_email or None,
        contact_phone=contact_phone or None,
        billing_address_line1=billing_address_line1 or None,
        billing_address_line2=billing_address_line2 or None,
        billing_city=billing_city or None,
        billing_state=billing_state or None,
        billing_postal_code=billing_postal_code or None,
        billing_country=billing_country or None,
        billing_gps_lat=billing_gps_lat if billing_gps_lat else None,
        billing_gps_lng=billing_gps_lng if billing_gps_lng else None,
        shipping_address_line1=shipping_address_line1 or None,
        shipping_address_line2=shipping_address_line2 or None,
        shipping_city=shipping_city or None,
        shipping_state=shipping_state or None,
        shipping_postal_code=shipping_postal_code or None,
        shipping_country=shipping_country or None,
        shipping_gps_lat=shipping_gps_lat if shipping_gps_lat else None,
        shipping_gps_lng=shipping_gps_lng if shipping_gps_lng else None,
        company=company,
        currency=currency,
        transaction_date=transaction_date,
        valid_till=valid_till,
        order_type=order_type or None,
        source=source or None,
        campaign=campaign or None,
        sales_partner_id=sales_partner_id,
        items=items,
        status=status,
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
        "customer_name": quotation.party_name or quotation.customer_name or "",
        "customer_account_id": str(quotation.customer_account_id) if quotation.customer_account_id else "",
        "lead_id": str(quotation.lead_id) if quotation.lead_id else "",
        "contact_name": quotation.contact_name or "",
        "contact_email": quotation.contact_email or "",
        "contact_phone": quotation.contact_phone or "",
        "billing_address_line1": quotation.billing_address_line1 or "",
        "billing_address_line2": quotation.billing_address_line2 or "",
        "billing_city": quotation.billing_city or "",
        "billing_state": quotation.billing_state or "",
        "billing_postal_code": quotation.billing_postal_code or "",
        "billing_country": quotation.billing_country or "",
        "billing_gps_lat": str(quotation.billing_gps_lat or ""),
        "billing_gps_lng": str(quotation.billing_gps_lng or ""),
        "shipping_address_line1": quotation.shipping_address_line1 or "",
        "shipping_address_line2": quotation.shipping_address_line2 or "",
        "shipping_city": quotation.shipping_city or "",
        "shipping_state": quotation.shipping_state or "",
        "shipping_postal_code": quotation.shipping_postal_code or "",
        "shipping_country": quotation.shipping_country or "",
        "shipping_gps_lat": str(quotation.shipping_gps_lat or ""),
        "shipping_gps_lng": str(quotation.shipping_gps_lng or ""),
        "company": quotation.company or "",
        "currency": quotation.currency or "NGN",
        "transaction_date": quotation.transaction_date.isoformat() if quotation.transaction_date else "",
        "valid_till": quotation.valid_till.isoformat() if quotation.valid_till else "",
        "order_type": quotation.order_type or "",
        "source": quotation.source or "",
        "campaign": quotation.campaign or "",
        "status": quotation.status.value if quotation.status else QuotationStatus.DRAFT.value,
        "sales_partner_id": str(quotation.sales_partner_id) if quotation.sales_partner_id else "",
    }
    context["status_options"] = get_quotation_status_options()
    context["customer_accounts"] = _get_customer_accounts(db)
    context["leads"] = _get_recent_leads(db)
    context["sales_people"] = _get_sales_people(db)
    context["tax_codes"] = _get_tax_codes(db)
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
    customer_name = _form_str(form, "customer_name") or _form_str(form, "party_name")
    party_name = customer_name
    customer_account_id = _form_int(form, "customer_account_id")
    lead_id = _form_int(form, "lead_id")
    contact_name = _form_str(form, "contact_name")
    contact_email = _form_str(form, "contact_email")
    contact_phone = _form_str(form, "contact_phone")
    billing_address_line1 = _form_str(form, "billing_address_line1")
    billing_address_line2 = _form_str(form, "billing_address_line2")
    billing_city = _form_str(form, "billing_city")
    billing_state = _form_str(form, "billing_state")
    billing_postal_code = _form_str(form, "billing_postal_code")
    billing_country = _form_str(form, "billing_country")
    billing_gps_lat = _form_decimal(form, "billing_gps_lat")
    billing_gps_lng = _form_decimal(form, "billing_gps_lng")
    shipping_address_line1 = _form_str(form, "shipping_address_line1")
    shipping_address_line2 = _form_str(form, "shipping_address_line2")
    shipping_city = _form_str(form, "shipping_city")
    shipping_state = _form_str(form, "shipping_state")
    shipping_postal_code = _form_str(form, "shipping_postal_code")
    shipping_country = _form_str(form, "shipping_country")
    shipping_gps_lat = _form_decimal(form, "shipping_gps_lat")
    shipping_gps_lng = _form_decimal(form, "shipping_gps_lng")
    company = _form_str(form, "company") or get_company_context(allow_null=True)
    currency = _form_str(form, "currency", "NGN") or "NGN"
    transaction_date = _form_date(_form_str(form, "transaction_date"))
    valid_till = _form_date(_form_str(form, "valid_till"))
    order_type = _form_str(form, "order_type")
    source = _form_str(form, "source")
    campaign = _form_str(form, "campaign")
    status = _form_str(form, "status", QuotationStatus.DRAFT.value)
    sales_partner_id = _form_int(form, "sales_partner_id")

    tax_codes = {tc.id: tc for tc in _get_tax_codes(db)}
    items = _parse_quote_line_items(form, tax_codes)

    errors: dict[str, str] = {}
    if not party_name and not customer_account_id and not lead_id:
        errors["customer_name"] = "Customer or lead name is required"
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
            "customer_name": customer_name,
            "customer_account_id": str(customer_account_id) if customer_account_id else "",
            "lead_id": str(lead_id) if lead_id else "",
            "contact_name": contact_name,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "billing_address_line1": billing_address_line1,
            "billing_address_line2": billing_address_line2,
            "billing_city": billing_city,
            "billing_state": billing_state,
            "billing_postal_code": billing_postal_code,
            "billing_country": billing_country,
            "billing_gps_lat": str(billing_gps_lat or ""),
            "billing_gps_lng": str(billing_gps_lng or ""),
            "shipping_address_line1": shipping_address_line1,
            "shipping_address_line2": shipping_address_line2,
            "shipping_city": shipping_city,
            "shipping_state": shipping_state,
            "shipping_postal_code": shipping_postal_code,
            "shipping_country": shipping_country,
            "shipping_gps_lat": str(shipping_gps_lat or ""),
            "shipping_gps_lng": str(shipping_gps_lng or ""),
            "company": company or "",
            "currency": currency,
            "transaction_date": _form_str(form, "transaction_date"),
            "valid_till": _form_str(form, "valid_till"),
            "order_type": order_type,
            "source": source,
            "campaign": campaign,
            "status": status,
            "sales_partner_id": str(sales_partner_id) if sales_partner_id else "",
        }
        context["status_options"] = get_quotation_status_options()
        context["customer_accounts"] = _get_customer_accounts(db)
        context["leads"] = _get_recent_leads(db)
        context["sales_people"] = _get_sales_people(db)
        context["tax_codes"] = list(tax_codes.values())
        context["errors"] = errors
        template = templates.get_template("modules/sales/templates/quotations/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    data = QuotationUpdateData(
        quotation_to=quotation_to,
        party_name=party_name,
        customer_name=customer_name or None,
        customer_account_id=customer_account_id,
        lead_id=lead_id,
        contact_name=contact_name or None,
        contact_email=contact_email or None,
        contact_phone=contact_phone or None,
        billing_address_line1=billing_address_line1 or None,
        billing_address_line2=billing_address_line2 or None,
        billing_city=billing_city or None,
        billing_state=billing_state or None,
        billing_postal_code=billing_postal_code or None,
        billing_country=billing_country or None,
        billing_gps_lat=billing_gps_lat if billing_gps_lat else None,
        billing_gps_lng=billing_gps_lng if billing_gps_lng else None,
        shipping_address_line1=shipping_address_line1 or None,
        shipping_address_line2=shipping_address_line2 or None,
        shipping_city=shipping_city or None,
        shipping_state=shipping_state or None,
        shipping_postal_code=shipping_postal_code or None,
        shipping_country=shipping_country or None,
        shipping_gps_lat=shipping_gps_lat if shipping_gps_lat else None,
        shipping_gps_lng=shipping_gps_lng if shipping_gps_lng else None,
        company=company,
        currency=currency,
        transaction_date=transaction_date,
        valid_till=valid_till,
        order_type=order_type or None,
        source=source or None,
        campaign=campaign or None,
        sales_partner_id=sales_partner_id,
        items=items,
        status=status,
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
    customer_account_id: Optional[int] = Query(None, description="Filter by customer account"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Sales orders list page."""
    # Use service for all data access
    service = SalesOrderService(db)

    # Build filters
    filters = (
        SalesOrderFilters(
            search=q,
            status=status,
            customer_account_id=customer_account_id,
        )
        if q or status or customer_account_id
        else None
    )

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
    context["current_customer_account_id"] = customer_account_id
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
    context["customer_accounts"] = _get_customer_accounts(db)

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
        "customer_account_id": "",
        "customer_name": "",
        "contact_name": "",
        "contact_email": "",
        "contact_phone": "",
        "billing_address_line1": "",
        "billing_address_line2": "",
        "billing_city": "",
        "billing_state": "",
        "billing_postal_code": "",
        "billing_country": "",
        "billing_gps_lat": "",
        "billing_gps_lng": "",
        "shipping_address_line1": "",
        "shipping_address_line2": "",
        "shipping_city": "",
        "shipping_state": "",
        "shipping_postal_code": "",
        "shipping_country": "",
        "shipping_gps_lat": "",
        "shipping_gps_lng": "",
        "quotation_id": "",
        "company": "",
        "currency": "NGN",
        "transaction_date": "",
        "delivery_date": "",
        "order_type": "",
        "source": "",
        "campaign": "",
        "sales_partner_id": "",
        "status": SalesOrderStatus.DRAFT.value,
    }
    context["status_options"] = get_order_status_options()
    context["customer_accounts"] = _get_customer_accounts(db)
    context["quotations"] = _get_recent_quotations(db)
    context["sales_people"] = _get_sales_people(db)
    context["tax_codes"] = _get_tax_codes(db)
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

    customer_name = _form_str(form, "customer_name")
    customer_account_id = _form_int(form, "customer_account_id")
    quotation_id = _form_int(form, "quotation_id")
    contact_name = _form_str(form, "contact_name")
    contact_email = _form_str(form, "contact_email")
    contact_phone = _form_str(form, "contact_phone")
    billing_address_line1 = _form_str(form, "billing_address_line1")
    billing_address_line2 = _form_str(form, "billing_address_line2")
    billing_city = _form_str(form, "billing_city")
    billing_state = _form_str(form, "billing_state")
    billing_postal_code = _form_str(form, "billing_postal_code")
    billing_country = _form_str(form, "billing_country")
    billing_gps_lat = _form_decimal(form, "billing_gps_lat")
    billing_gps_lng = _form_decimal(form, "billing_gps_lng")
    shipping_address_line1 = _form_str(form, "shipping_address_line1")
    shipping_address_line2 = _form_str(form, "shipping_address_line2")
    shipping_city = _form_str(form, "shipping_city")
    shipping_state = _form_str(form, "shipping_state")
    shipping_postal_code = _form_str(form, "shipping_postal_code")
    shipping_country = _form_str(form, "shipping_country")
    shipping_gps_lat = _form_decimal(form, "shipping_gps_lat")
    shipping_gps_lng = _form_decimal(form, "shipping_gps_lng")
    billing_address = _form_str(form, "billing_address")
    shipping_address = _form_str(form, "shipping_address")
    company = _form_str(form, "company") or get_company_context(allow_null=True)
    currency = _form_str(form, "currency", "NGN") or "NGN"
    transaction_date = _form_date(_form_str(form, "transaction_date"))
    delivery_date = _form_date(_form_str(form, "delivery_date"))
    order_type = _form_str(form, "order_type")
    source = _form_str(form, "source")
    campaign = _form_str(form, "campaign")
    status = _form_str(form, "status", SalesOrderStatus.DRAFT.value)
    sales_partner_id = _form_int(form, "sales_partner_id")

    tax_codes = {tc.id: tc for tc in _get_tax_codes(db)}
    items = _parse_line_items(form, tax_codes)
    if not items:
        items = None

    errors: dict[str, str] = {}
    if not customer_account_id and not customer_name and not quotation_id:
        errors["customer"] = "Customer is required"
    if not items and not quotation_id:
        errors["items"] = "At least one line item is required"
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
            "customer_name": customer_name,
            "customer_account_id": str(customer_account_id) if customer_account_id else "",
            "quotation_id": str(quotation_id) if quotation_id else "",
            "contact_name": contact_name,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "billing_address_line1": billing_address_line1,
            "billing_address_line2": billing_address_line2,
            "billing_city": billing_city,
            "billing_state": billing_state,
            "billing_postal_code": billing_postal_code,
            "billing_country": billing_country,
            "billing_gps_lat": str(billing_gps_lat or ""),
            "billing_gps_lng": str(billing_gps_lng or ""),
            "shipping_address_line1": shipping_address_line1,
            "shipping_address_line2": shipping_address_line2,
            "shipping_city": shipping_city,
            "shipping_state": shipping_state,
            "shipping_postal_code": shipping_postal_code,
            "shipping_country": shipping_country,
            "shipping_gps_lat": str(shipping_gps_lat or ""),
            "shipping_gps_lng": str(shipping_gps_lng or ""),
            "company": company,
            "currency": currency,
            "transaction_date": _form_str(form, "transaction_date"),
            "delivery_date": _form_str(form, "delivery_date"),
            "order_type": order_type,
            "source": source,
            "campaign": campaign,
            "sales_partner_id": str(sales_partner_id) if sales_partner_id else "",
            "status": status,
        }
        context["status_options"] = get_order_status_options()
        context["customer_accounts"] = _get_customer_accounts(db)
        context["quotations"] = _get_recent_quotations(db)
        context["sales_people"] = _get_sales_people(db)
        context["tax_codes"] = list(tax_codes.values())
        context["errors"] = errors
        template = templates.get_template("modules/sales/templates/orders/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    data = SalesOrderCreateData(
        customer_name=customer_name or None,
        customer_account_id=customer_account_id,
        contact_name=contact_name or None,
        contact_email=contact_email or None,
        contact_phone=contact_phone or None,
        billing_address_line1=billing_address_line1 or None,
        billing_address_line2=billing_address_line2 or None,
        billing_city=billing_city or None,
        billing_state=billing_state or None,
        billing_postal_code=billing_postal_code or None,
        billing_country=billing_country or None,
        billing_gps_lat=billing_gps_lat if billing_gps_lat else None,
        billing_gps_lng=billing_gps_lng if billing_gps_lng else None,
        shipping_address_line1=shipping_address_line1 or None,
        shipping_address_line2=shipping_address_line2 or None,
        shipping_city=shipping_city or None,
        shipping_state=shipping_state or None,
        shipping_postal_code=shipping_postal_code or None,
        shipping_country=shipping_country or None,
        shipping_gps_lat=shipping_gps_lat if shipping_gps_lat else None,
        shipping_gps_lng=shipping_gps_lng if shipping_gps_lng else None,
        quotation_id=quotation_id,
        company=company or None,
        currency=currency,
        transaction_date=transaction_date,
        delivery_date=delivery_date,
        order_type=order_type or None,
        source=source or None,
        campaign=campaign or None,
        sales_partner_id=sales_partner_id,
        items=items,
        status=status,
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
        "customer_name": order.customer_name or "",
        "customer_account_id": str(order.customer_account_id) if order.customer_account_id else "",
        "quotation_id": str(order.quotation_id) if order.quotation_id else "",
        "contact_name": order.contact_name or "",
        "contact_email": order.contact_email or "",
        "contact_phone": order.contact_phone or "",
        "billing_address_line1": order.billing_address_line1 or "",
        "billing_address_line2": order.billing_address_line2 or "",
        "billing_city": order.billing_city or "",
        "billing_state": order.billing_state or "",
        "billing_postal_code": order.billing_postal_code or "",
        "billing_country": order.billing_country or "",
        "billing_gps_lat": str(order.billing_gps_lat) if order.billing_gps_lat else "",
        "billing_gps_lng": str(order.billing_gps_lng) if order.billing_gps_lng else "",
        "shipping_address_line1": order.shipping_address_line1 or "",
        "shipping_address_line2": order.shipping_address_line2 or "",
        "shipping_city": order.shipping_city or "",
        "shipping_state": order.shipping_state or "",
        "shipping_postal_code": order.shipping_postal_code or "",
        "shipping_country": order.shipping_country or "",
        "shipping_gps_lat": str(order.shipping_gps_lat) if order.shipping_gps_lat else "",
        "shipping_gps_lng": str(order.shipping_gps_lng) if order.shipping_gps_lng else "",
        "company": order.company or "",
        "currency": order.currency or "NGN",
        "transaction_date": order.transaction_date.isoformat() if order.transaction_date else "",
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else "",
        "order_type": order.order_type or "",
        "source": order.source or "",
        "campaign": order.campaign or "",
        "sales_partner_id": str(order.sales_partner_id) if order.sales_partner_id else "",
        "status": order.status.value if order.status else SalesOrderStatus.DRAFT.value,
    }
    context["status_options"] = get_order_status_options()
    context["customer_accounts"] = _get_customer_accounts(db)
    context["quotations"] = _get_recent_quotations(db)
    context["sales_people"] = _get_sales_people(db)
    context["tax_codes"] = _get_tax_codes(db)
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
    customer_account_id = _form_int(form, "customer_account_id")
    quotation_id = _form_int(form, "quotation_id")
    contact_name = _form_str(form, "contact_name")
    contact_email = _form_str(form, "contact_email")
    contact_phone = _form_str(form, "contact_phone")
    billing_address = _form_str(form, "billing_address")
    shipping_address = _form_str(form, "shipping_address")
    delivery_date = _form_date(_form_str(form, "delivery_date"))
    order_type = _form_str(form, "order_type")
    source = _form_str(form, "source")
    campaign = _form_str(form, "campaign")
    status = _form_str(form, "status", SalesOrderStatus.DRAFT.value)
    sales_partner_id = _form_int(form, "sales_partner_id")

    tax_codes = {tc.id: tc for tc in _get_tax_codes(db)}
    items = _parse_line_items(form, tax_codes)

    data = SalesOrderUpdateData(
        customer_name=customer_name or None,
        customer_account_id=customer_account_id,
        contact_name=contact_name or None,
        contact_email=contact_email or None,
        contact_phone=contact_phone or None,
        billing_address=billing_address or None,
        shipping_address=shipping_address or None,
        delivery_date=delivery_date,
        order_type=order_type or None,
        sales_partner_id=sales_partner_id,
        source=source or None,
        campaign=campaign or None,
        quotation_id=quotation_id,
        status=status,
        items=items,
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
            "customer_name": customer_name,
            "customer_account_id": str(customer_account_id) if customer_account_id else "",
            "quotation_id": str(quotation_id) if quotation_id else "",
            "contact_name": contact_name,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "billing_address_line1": billing_address_line1,
            "billing_address_line2": billing_address_line2,
            "billing_city": billing_city,
            "billing_state": billing_state,
            "billing_postal_code": billing_postal_code,
            "billing_country": billing_country,
            "billing_gps_lat": str(billing_gps_lat or ""),
            "billing_gps_lng": str(billing_gps_lng or ""),
            "shipping_address_line1": shipping_address_line1,
            "shipping_address_line2": shipping_address_line2,
            "shipping_city": shipping_city,
            "shipping_state": shipping_state,
            "shipping_postal_code": shipping_postal_code,
            "shipping_country": shipping_country,
            "shipping_gps_lat": str(shipping_gps_lat or ""),
            "shipping_gps_lng": str(shipping_gps_lng or ""),
            "company": order.company or "",
            "currency": order.currency or "NGN",
            "transaction_date": order.transaction_date.isoformat() if order.transaction_date else "",
            "delivery_date": _form_str(form, "delivery_date"),
            "order_type": order_type,
            "source": source,
            "campaign": campaign,
            "sales_partner_id": str(sales_partner_id) if sales_partner_id else "",
            "status": status,
        }
        context["status_options"] = get_order_status_options()
        context["customer_accounts"] = _get_customer_accounts(db)
        context["quotations"] = _get_recent_quotations(db)
        context["sales_people"] = _get_sales_people(db)
        context["tax_codes"] = list(tax_codes.values())
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
