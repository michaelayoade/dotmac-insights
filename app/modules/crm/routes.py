"""
CRM Module Routes - Leads, Opportunities, Activities, Campaigns.

HTMX-powered routes for CRM management.
All routes delegate to services for business logic.
"""
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Request, Response, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.web.dependencies import SessionUser, CSRFToken, DB
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.core.security import validate_csrf, set_flash

# Services
from app.services.crm import (
    LeadService,
    OpportunityService,
    ActivityService,
    CampaignService,
)
from app.services.crm.lead_types import LeadCreateData, LeadFilters
from app.services.crm.opportunity_types import OpportunityFilters
from app.services.crm.activity_types import ActivityFilters
from app.services.crm.campaign_types import CampaignFilters
from app.services.types import PaginationParams
from app.services.errors import NotFoundError, ValidationError, ConflictError
from app.services.identity import PartyService
from app.services.identity.party_types import (
    PartyFilters,
    PartyCreateData,
    PartyUpdateData,
    PartyRoleCreateData,
)

router = APIRouter()
templates = get_template_env()


# =============================================================================
# Service Providers
# =============================================================================

def get_lead_service(db: Session) -> LeadService:
    return LeadService(db)


def get_opportunity_service(db: Session) -> OpportunityService:
    return OpportunityService(db)


def get_activity_service(db: Session) -> ActivityService:
    return ActivityService(db)


def get_campaign_service(db: Session) -> CampaignService:
    return CampaignService(db)


# =============================================================================
# Contacts Helpers
# =============================================================================

CONTACT_TYPE_OPTIONS = [
    {"value": "lead", "label": "Lead"},
    {"value": "prospect", "label": "Prospect"},
    {"value": "customer", "label": "Customer"},
    {"value": "churned", "label": "Churned"},
]

CONTACT_STATUS_OPTIONS = [
    {"value": "active", "label": "Active"},
    {"value": "inactive", "label": "Inactive"},
    {"value": "suspended", "label": "Suspended"},
]

CONTACT_CATEGORY_OPTIONS = [
    {"value": "business", "label": "Business"},
    {"value": "personal", "label": "Personal"},
    {"value": "partner", "label": "Partner"},
]


def get_party_service(db: Session, user: SessionUser) -> PartyService:
    return PartyService(db, principal=user)


def _status_filter(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if value == "suspended":
        return "blocked"
    return value


def _get_contact_type(party) -> str:
    for role in party.roles or []:
        if role.until is None and role.role:
            return role.role
    if party.custom_fields and isinstance(party.custom_fields, dict):
        return party.custom_fields.get("contact_type", "") or ""
    return ""


def _get_contact_category(party) -> str:
    if party.custom_fields and isinstance(party.custom_fields, dict):
        return party.custom_fields.get("category", "") or ""
    return ""


# =============================================================================
# Accounts Routes (Organizations)
# =============================================================================

ACCOUNT_TYPE_OPTIONS = [
    {"value": "customer", "label": "Customer"},
    {"value": "prospect", "label": "Prospect"},
    {"value": "partner", "label": "Partner"},
    {"value": "vendor", "label": "Vendor"},
]


@router.get("/crm/accounts", response_class=HTMLResponse)
async def accounts_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    account_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """List accounts (organizations) using PartyService."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Accounts"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm"},
        {"label": "Accounts"},
    ])

    if status is None:
        status_filter = "active"
        current_status = "active"
    elif status == "":
        status_filter = None
        current_status = ""
    else:
        status_filter = status
        current_status = status

    filters = PartyFilters(
        party_type="organization",
        status=_status_filter(status_filter) if status_filter else None,
        search=q,
        has_role=account_type,
    )
    pagination = PaginationParams(
        offset=(page - 1) * per_page,
        limit=per_page,
    )
    service = get_party_service(db, user)
    result = service.list_parties(filters, pagination, include_roles=True)

    accounts = result.items
    for account in accounts:
        account.account_type = _get_contact_type(account)

    context["accounts"] = accounts
    context["search_query"] = q or ""
    context["current_type"] = account_type or ""
    context["current_status"] = current_status
    context["type_options"] = ACCOUNT_TYPE_OPTIONS
    context["status_options"] = CONTACT_STATUS_OPTIONS
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    if request.headers.get("HX-Request"):
        template = templates.get_template("modules/crm/templates/accounts/partials/accounts_table.html")
        return HTMLResponse(template.render(context))

    template = templates.get_template("modules/crm/templates/accounts/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/accounts/new", response_class=HTMLResponse)
async def accounts_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New account form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Account"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm"},
        {"label": "Accounts", "href": "/crm/accounts"},
        {"label": "New"},
    ])
    context["type_options"] = ACCOUNT_TYPE_OPTIONS
    context["form_data"] = {}
    context["errors"] = {}

    template = templates.get_template("modules/crm/templates/accounts/pages/form.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/accounts/{account_id}", response_class=HTMLResponse)
async def account_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    account_id: int,
):
    """View account details."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)

    service = get_party_service(db, user)
    try:
        account = service.get_party(account_id, include_roles=True)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Account not found")

    if account.type != "organization":
        raise HTTPException(status_code=404, detail="Account not found")

    context["page_title"] = account.name or f"Account #{account_id}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm"},
        {"label": "Accounts", "href": "/crm/accounts"},
        {"label": account.name or f"#{account_id}"},
    ])
    context["account"] = account

    template = templates.get_template("modules/crm/templates/accounts/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.post("/crm/accounts", response_class=HTMLResponse)
async def accounts_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Create a new account."""
    await validate_csrf(request)
    form = await request.form()

    name = (form.get("name") or "").strip()
    legal_name = (form.get("legal_name") or "").strip()
    trading_name = (form.get("trading_name") or "").strip()
    email = (form.get("email") or "").strip()
    phone = (form.get("phone") or "").strip()
    account_type = (form.get("account_type") or "").strip()
    tax_id = (form.get("tax_id") or "").strip()
    registration_number = (form.get("registration_number") or "").strip()
    website = (form.get("website") or "").strip()
    industry = (form.get("industry") or "").strip()
    notes = (form.get("notes") or "").strip()

    errors: dict[str, str] = {}
    if not name and not legal_name:
        errors["name"] = "Name or Legal Name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Account"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm"},
            {"label": "Accounts", "href": "/crm/accounts"},
            {"label": "New"},
        ])
        context["type_options"] = ACCOUNT_TYPE_OPTIONS
        context["form_data"] = {
            "name": name,
            "legal_name": legal_name,
            "trading_name": trading_name,
            "email": email,
            "phone": phone,
            "account_type": account_type,
            "tax_id": tax_id,
            "registration_number": registration_number,
            "website": website,
            "industry": industry,
            "notes": notes,
        }
        context["errors"] = errors
        template = templates.get_template("modules/crm/templates/accounts/pages/form.html")
        return HTMLResponse(template.render(context))

    service = get_party_service(db, user)
    create_data = PartyCreateData(
        type="organization",
        name=name or legal_name,
        legal_name=legal_name or None,
        trading_name=trading_name or None,
        primary_email=email or None,
        primary_phone=phone or None,
        tax_id=tax_id or None,
        registration_number=registration_number or None,
        website=website or None,
        industry=industry or None,
        notes=notes or None,
    )

    try:
        account = service.create_party(create_data)
        if account_type:
            service.add_party_role(account.id, PartyRoleCreateData(role=account_type))
        db.commit()
    except ValidationError as exc:
        db.rollback()
        errors["general"] = str(exc)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Account"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm"},
            {"label": "Accounts", "href": "/crm/accounts"},
            {"label": "New"},
        ])
        context["type_options"] = ACCOUNT_TYPE_OPTIONS
        context["form_data"] = {
            "name": name,
            "legal_name": legal_name,
            "trading_name": trading_name,
            "email": email,
            "phone": phone,
            "account_type": account_type,
            "tax_id": tax_id,
            "registration_number": registration_number,
            "website": website,
            "industry": industry,
            "notes": notes,
        }
        context["errors"] = errors
        template = templates.get_template("modules/crm/templates/accounts/pages/form.html")
        return HTMLResponse(template.render(context))

    redirect = RedirectResponse(url=f"/crm/accounts/{account.id}", status_code=303)
    set_flash(redirect, "Account created successfully.", "success")
    return redirect


@router.get("/crm/accounts/{account_id}/edit", response_class=HTMLResponse)
async def accounts_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    account_id: int,
):
    """Edit account form."""
    service = get_party_service(db, user)
    try:
        account = service.get_party(account_id, include_roles=True)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Account not found") from exc

    if account.type != "organization":
        raise HTTPException(status_code=404, detail="Account not found")

    account_type = _get_contact_type(account)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Edit Account"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm"},
        {"label": "Accounts", "href": "/crm/accounts"},
        {"label": account.name or f"Account {account.id}", "href": f"/crm/accounts/{account.id}"},
        {"label": "Edit"},
    ])
    context["type_options"] = ACCOUNT_TYPE_OPTIONS
    context["form_data"] = {
        "name": account.name or "",
        "legal_name": account.legal_name or "",
        "trading_name": account.trading_name or "",
        "email": account.primary_email or "",
        "phone": account.primary_phone or "",
        "account_type": account_type,
        "tax_id": account.tax_id or "",
        "registration_number": account.registration_number or "",
        "website": account.website or "",
        "industry": account.industry or "",
        "notes": account.notes or "",
    }
    context["errors"] = {}
    context["account"] = account

    template = templates.get_template("modules/crm/templates/accounts/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/crm/accounts/{account_id}", response_class=HTMLResponse)
async def accounts_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    account_id: int,
):
    """Update an account."""
    await validate_csrf(request)
    form = await request.form()

    name = (form.get("name") or "").strip()
    legal_name = (form.get("legal_name") or "").strip()
    trading_name = (form.get("trading_name") or "").strip()
    email = (form.get("email") or "").strip()
    phone = (form.get("phone") or "").strip()
    account_type = (form.get("account_type") or "").strip()
    tax_id = (form.get("tax_id") or "").strip()
    registration_number = (form.get("registration_number") or "").strip()
    website = (form.get("website") or "").strip()
    industry = (form.get("industry") or "").strip()
    notes = (form.get("notes") or "").strip()

    errors: dict[str, str] = {}
    if not name and not legal_name:
        errors["name"] = "Name or Legal Name is required"

    service = get_party_service(db, user)
    try:
        account = service.get_party(account_id, include_roles=True)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Account not found") from exc

    if account.type != "organization":
        raise HTTPException(status_code=404, detail="Account not found")

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Account"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm"},
            {"label": "Accounts", "href": "/crm/accounts"},
            {"label": account.name or f"Account {account.id}", "href": f"/crm/accounts/{account.id}"},
            {"label": "Edit"},
        ])
        context["type_options"] = ACCOUNT_TYPE_OPTIONS
        context["form_data"] = {
            "name": name,
            "legal_name": legal_name,
            "trading_name": trading_name,
            "email": email,
            "phone": phone,
            "account_type": account_type,
            "tax_id": tax_id,
            "registration_number": registration_number,
            "website": website,
            "industry": industry,
            "notes": notes,
        }
        context["errors"] = errors
        context["account"] = account
        template = templates.get_template("modules/crm/templates/accounts/pages/form.html")
        return HTMLResponse(template.render(context))

    update_data = PartyUpdateData(
        name=name or legal_name,
        legal_name=legal_name or None,
        trading_name=trading_name or None,
        primary_email=email or None,
        primary_phone=phone or None,
        tax_id=tax_id or None,
        registration_number=registration_number or None,
        website=website or None,
        industry=industry or None,
        notes=notes or None,
    )

    try:
        service.update_party(account_id, update_data)
        if account_type:
            existing_role = None
            for role in account.roles or []:
                if role.until is None:
                    existing_role = role
                    break
            if existing_role and existing_role.role != account_type:
                service.remove_party_role(account_id, existing_role.id)
                service.add_party_role(account_id, PartyRoleCreateData(role=account_type))
            elif not existing_role:
                service.add_party_role(account_id, PartyRoleCreateData(role=account_type))
        db.commit()
    except ValidationError as exc:
        db.rollback()
        errors["general"] = str(exc)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Account"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm"},
            {"label": "Accounts", "href": "/crm/accounts"},
            {"label": account.name or f"Account {account.id}", "href": f"/crm/accounts/{account.id}"},
            {"label": "Edit"},
        ])
        context["type_options"] = ACCOUNT_TYPE_OPTIONS
        context["form_data"] = {
            "name": name,
            "legal_name": legal_name,
            "trading_name": trading_name,
            "email": email,
            "phone": phone,
            "account_type": account_type,
            "tax_id": tax_id,
            "registration_number": registration_number,
            "website": website,
            "industry": industry,
            "notes": notes,
        }
        context["errors"] = errors
        context["account"] = account
        template = templates.get_template("modules/crm/templates/accounts/pages/form.html")
        return HTMLResponse(template.render(context))

    redirect = RedirectResponse(url=f"/crm/accounts/{account_id}", status_code=303)
    set_flash(redirect, "Account updated successfully.", "success")
    return redirect


@router.post("/crm/accounts/{account_id}/delete", response_class=HTMLResponse)
async def accounts_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    account_id: int,
):
    """Delete an account (soft delete)."""
    await validate_csrf(request)
    service = get_party_service(db, user)
    try:
        account = service.get_party(account_id)
        if account.type != "organization":
            raise HTTPException(status_code=404, detail="Account not found")
        service.delete_party(account_id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    redirect = RedirectResponse(url="/crm/accounts", status_code=303)
    set_flash(redirect, "Account deleted successfully.", "success")
    return redirect


@router.delete("/crm/accounts/bulk-delete", response_class=JSONResponse)
async def accounts_bulk_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Bulk delete accounts (soft delete)."""
    await validate_csrf(request)
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    ids = payload.get("ids", [])
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="Invalid payload")

    service = get_party_service(db, user)
    deleted = 0
    for account_id in ids:
        try:
            account = service.get_party(int(account_id))
            if account.type == "organization":
                service.delete_party(int(account_id))
                deleted += 1
        except (ValueError, NotFoundError):
            continue
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return JSONResponse({"deleted": deleted})


# =============================================================================
# Contacts Routes (People)
# =============================================================================

@router.get("/crm/contacts", response_class=HTMLResponse)
async def contacts_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    contact_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """List contacts (people) using PartyService."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Contacts"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm"},
        {"label": "Contacts"},
    ])

    if status is None:
        status_filter = "active"
        current_status = "active"
    elif status == "":
        status_filter = None
        current_status = ""
    else:
        status_filter = status
        current_status = status

    filters = PartyFilters(
        party_type="person",
        status=_status_filter(status_filter) if status_filter else None,
        search=q,
        has_role=contact_type,
    )
    pagination = PaginationParams(
        offset=(page - 1) * per_page,
        limit=per_page,
    )
    service = get_party_service(db, user)
    result = service.list_parties(filters, pagination, include_roles=True)

    contacts = result.items
    for contact in contacts:
        contact.contact_type = _get_contact_type(contact)
        contact.contact_category = _get_contact_category(contact)

    context["contacts"] = contacts
    context["search_query"] = q or ""
    context["current_type"] = contact_type or ""
    context["current_status"] = current_status
    context["type_options"] = CONTACT_TYPE_OPTIONS
    context["status_options"] = CONTACT_STATUS_OPTIONS
    context["pagination"] = build_pagination_context(page, per_page, result.total)

    if request.headers.get("HX-Request"):
        template = templates.get_template("modules/crm/templates/contacts/partials/contacts_table.html")
        return HTMLResponse(template.render(context))

    template = templates.get_template("modules/crm/templates/contacts/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/contacts/table", response_class=HTMLResponse)
async def contacts_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    contact_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Contacts table partial for HTMX updates."""
    return await contacts_list(
        request,
        response,
        user,
        csrf_token,
        db,
        q,
        contact_type,
        status,
        page,
        per_page,
    )


@router.get("/crm/contacts/new", response_class=HTMLResponse)
async def contacts_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New contact form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Contact"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm"},
        {"label": "Contacts", "href": "/crm/contacts"},
        {"label": "New"},
    ])
    context["type_options"] = CONTACT_TYPE_OPTIONS
    context["category_options"] = CONTACT_CATEGORY_OPTIONS
    context["form_data"] = {}
    context["errors"] = {}

    template = templates.get_template("modules/crm/templates/contacts/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/crm/contacts", response_class=HTMLResponse)
async def contacts_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Create a new contact."""
    await validate_csrf(request)
    form = await request.form()

    name = (form.get("name") or "").strip()
    email = (form.get("email") or "").strip()
    phone = (form.get("phone") or "").strip()
    contact_type = (form.get("contact_type") or "").strip()
    category = (form.get("category") or "").strip()
    company_name = (form.get("company_name") or "").strip()

    errors: dict[str, str] = {}
    if not name:
        errors["name"] = "Name is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Contact"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm"},
            {"label": "Contacts", "href": "/crm/contacts"},
            {"label": "New"},
        ])
        context["type_options"] = CONTACT_TYPE_OPTIONS
        context["category_options"] = CONTACT_CATEGORY_OPTIONS
        context["form_data"] = {
            "name": name,
            "email": email,
            "phone": phone,
            "contact_type": contact_type,
            "category": category,
            "company_name": company_name,
        }
        context["errors"] = errors
        template = templates.get_template("modules/crm/templates/contacts/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    service = get_party_service(db, user)

    emails = [{"address": email, "is_primary": True}] if email else []
    phones = [{"number": phone, "is_primary": True}] if phone else []
    custom_fields = {
        "category": category or None,
        "company_name": company_name or None,
        "contact_type": contact_type or None,
    }

    try:
        party = service.create_party(PartyCreateData(
            type="person",
            name=name,
            status="active",
            emails=emails,
            phones=phones,
            custom_fields=custom_fields,
        ))
        if contact_type:
            try:
                service.add_role(party.id, PartyRoleCreateData(role=contact_type))
            except ConflictError:
                pass
        db.commit()
    except (ValidationError, ConflictError) as exc:
        db.rollback()
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Contact"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm"},
            {"label": "Contacts", "href": "/crm/contacts"},
            {"label": "New"},
        ])
        context["type_options"] = CONTACT_TYPE_OPTIONS
        context["category_options"] = CONTACT_CATEGORY_OPTIONS
        context["form_data"] = {
            "name": name,
            "email": email,
            "phone": phone,
            "contact_type": contact_type,
            "category": category,
            "company_name": company_name,
        }
        context["errors"] = {"form": str(exc)}
        template = templates.get_template("modules/crm/templates/contacts/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    redirect = RedirectResponse(url=f"/crm/contacts/{party.id}", status_code=303)
    set_flash(redirect, "Contact created successfully.", "success")
    return redirect


@router.get("/crm/contacts/{contact_id}", response_class=HTMLResponse)
async def contacts_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    contact_id: int,
):
    """Contact detail page."""
    service = get_party_service(db, user)
    try:
        contact = service.get_party(contact_id, include_roles=True)
    except NotFoundError:
        context = get_base_context(request, response, user, csrf_token)
        context["error"] = "Contact not found"
        template = templates.get_template("modules/crm/templates/contacts/pages/detail.html")
        return HTMLResponse(template.render(context), status_code=404)

    contact.contact_type = _get_contact_type(contact)
    contact.contact_category = _get_contact_category(contact)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = contact.name or "Contact"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm"},
        {"label": "Contacts", "href": "/crm/contacts"},
        {"label": contact.name or f"Contact {contact.id}"},
    ])
    context["contact"] = contact

    template = templates.get_template("modules/crm/templates/contacts/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/contacts/{contact_id}/edit", response_class=HTMLResponse)
async def contacts_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    contact_id: int,
):
    """Edit contact form."""
    service = get_party_service(db, user)
    try:
        contact = service.get_party(contact_id, include_roles=True)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Contact not found") from exc

    contact_type = _get_contact_type(contact)
    category = _get_contact_category(contact)
    company_name = ""
    if contact.custom_fields and isinstance(contact.custom_fields, dict):
        company_name = contact.custom_fields.get("company_name", "") or ""

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Edit Contact"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm"},
        {"label": "Contacts", "href": "/crm/contacts"},
        {"label": contact.name or f"Contact {contact.id}", "href": f"/crm/contacts/{contact.id}"},
        {"label": "Edit"},
    ])
    context["type_options"] = CONTACT_TYPE_OPTIONS
    context["category_options"] = CONTACT_CATEGORY_OPTIONS
    context["form_data"] = {
        "name": contact.name or "",
        "email": contact.primary_email or "",
        "phone": contact.primary_phone or "",
        "contact_type": contact_type,
        "category": category,
        "company_name": company_name,
    }
    context["errors"] = {}
    context["contact"] = contact

    template = templates.get_template("modules/crm/templates/contacts/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/crm/contacts/{contact_id}", response_class=HTMLResponse)
async def contacts_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    contact_id: int,
):
    """Update a contact."""
    await validate_csrf(request)
    form = await request.form()

    name = (form.get("name") or "").strip()
    email = (form.get("email") or "").strip()
    phone = (form.get("phone") or "").strip()
    contact_type = (form.get("contact_type") or "").strip()
    category = (form.get("category") or "").strip()
    company_name = (form.get("company_name") or "").strip()

    errors: dict[str, str] = {}
    if not name:
        errors["name"] = "Name is required"

    service = get_party_service(db, user)
    try:
        contact = service.get_party(contact_id, include_roles=True)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Contact not found") from exc

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Contact"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm"},
            {"label": "Contacts", "href": "/crm/contacts"},
            {"label": contact.name or f"Contact {contact.id}", "href": f"/crm/contacts/{contact.id}"},
            {"label": "Edit"},
        ])
        context["type_options"] = CONTACT_TYPE_OPTIONS
        context["category_options"] = CONTACT_CATEGORY_OPTIONS
        context["form_data"] = {
            "name": name,
            "email": email,
            "phone": phone,
            "contact_type": contact_type,
            "category": category,
            "company_name": company_name,
        }
        context["errors"] = errors
        context["contact"] = contact
        template = templates.get_template("modules/crm/templates/contacts/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    emails = [{"address": email, "is_primary": True}] if email else []
    phones = [{"number": phone, "is_primary": True}] if phone else []
    custom_fields = {
        "category": category or None,
        "company_name": company_name or None,
        "contact_type": contact_type or None,
    }

    try:
        service.update_party(contact_id, PartyUpdateData(
            name=name,
            emails=emails,
            phones=phones,
            custom_fields=custom_fields,
        ))
        if contact_type and contact_type != _get_contact_type(contact):
            try:
                service.add_role(contact_id, PartyRoleCreateData(role=contact_type))
            except ConflictError:
                pass
        db.commit()
    except (ValidationError, ConflictError) as exc:
        db.rollback()
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "Edit Contact"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm"},
            {"label": "Contacts", "href": "/crm/contacts"},
            {"label": contact.name or f"Contact {contact.id}", "href": f"/crm/contacts/{contact.id}"},
            {"label": "Edit"},
        ])
        context["type_options"] = CONTACT_TYPE_OPTIONS
        context["category_options"] = CONTACT_CATEGORY_OPTIONS
        context["form_data"] = {
            "name": name,
            "email": email,
            "phone": phone,
            "contact_type": contact_type,
            "category": category,
            "company_name": company_name,
        }
        context["errors"] = {"form": str(exc)}
        context["contact"] = contact
        template = templates.get_template("modules/crm/templates/contacts/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    redirect = RedirectResponse(url=f"/crm/contacts/{contact_id}", status_code=303)
    set_flash(redirect, "Contact updated successfully.", "success")
    return redirect


@router.post("/crm/contacts/{contact_id}/delete", response_class=HTMLResponse)
async def contacts_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    contact_id: int,
):
    """Delete a contact (soft delete)."""
    await validate_csrf(request)
    service = get_party_service(db, user)
    try:
        service.delete_party(contact_id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    redirect = RedirectResponse(url="/crm/contacts", status_code=303)
    set_flash(redirect, "Contact deleted successfully.", "success")
    return redirect


@router.delete("/crm/contacts/bulk-delete", response_class=JSONResponse)
async def contacts_bulk_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Bulk delete contacts (soft delete)."""
    await validate_csrf(request)
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    ids = payload.get("ids", [])
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="Invalid payload")

    service = get_party_service(db, user)
    deleted = 0
    for contact_id in ids:
        try:
            service.delete_party(int(contact_id))
            deleted += 1
        except (ValueError, NotFoundError):
            continue
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return JSONResponse({"deleted": deleted})


@router.get("/crm/contacts/{contact_id}/tabs/{tab_name}", response_class=HTMLResponse)
async def contacts_tab(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    contact_id: int,
    tab_name: str,
):
    """Contact tab content partial."""
    service = get_party_service(db, user)
    try:
        contact = service.get_party(contact_id, include_roles=True)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Contact not found") from exc

    context = get_base_context(request, response, user, csrf_token)
    context["contact"] = contact

    if tab_name == "activity":
        template = templates.get_template("modules/crm/templates/contacts/partials/tab_activity.html")
    else:
        template = templates.get_template("modules/crm/templates/contacts/partials/tab_overview.html")

    return HTMLResponse(template.render(context))

# =============================================================================
# Leads Routes
# =============================================================================

@router.get("/crm/leads", response_class=HTMLResponse)
async def leads_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    status: Optional[str] = None,
    qualification: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """List leads using LeadService."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Leads"
    context["now"] = datetime.utcnow()

    per_page = 25
    lead_service = get_lead_service(db)

    filters = LeadFilters(
        search=search,
        status=status,
        qualification=qualification,
    )
    pagination = PaginationParams(
        offset=(page - 1) * per_page,
        limit=per_page,
    )

    result = lead_service.list_leads(filters, pagination)

    context["leads"] = result.items
    context["total"] = result.total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (result.total + per_page - 1) // per_page
    context["search"] = search or ""
    context["status_filter"] = status
    context["qualification_filter"] = qualification

    context["status_options"] = [
        {"value": "active", "label": "Active"},
        {"value": "qualified", "label": "Qualified"},
        {"value": "disqualified", "label": "Disqualified"},
        {"value": "converted", "label": "Converted"},
    ]

    context["qualification_options"] = [
        {"value": "hot", "label": "Hot"},
        {"value": "warm", "label": "Warm"},
        {"value": "cold", "label": "Cold"},
    ]

    template = templates.get_template("modules/crm/templates/leads/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/leads/table", response_class=HTMLResponse)
async def leads_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """HTMX partial - leads table using LeadService."""
    context = get_base_context(request, response, user, csrf_token)
    per_page = 25

    lead_service = get_lead_service(db)
    filters = LeadFilters(search=search, status=status)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = lead_service.list_leads(filters, pagination)

    context["leads"] = result.items
    context["total"] = result.total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (result.total + per_page - 1) // per_page

    template = templates.get_template("modules/crm/templates/leads/partials/leads_table.html")
    return HTMLResponse(template.render(context))


LEAD_SOURCE_OPTIONS = [
    {"value": "website", "label": "Website"},
    {"value": "referral", "label": "Referral"},
    {"value": "advertisement", "label": "Advertisement"},
    {"value": "cold_call", "label": "Cold Call"},
    {"value": "email_campaign", "label": "Email Campaign"},
    {"value": "social_media", "label": "Social Media"},
    {"value": "trade_show", "label": "Trade Show"},
    {"value": "partner", "label": "Partner"},
    {"value": "other", "label": "Other"},
]

LEAD_QUALIFICATION_OPTIONS = [
    {"value": "hot", "label": "Hot"},
    {"value": "warm", "label": "Warm"},
    {"value": "cold", "label": "Cold"},
]


@router.get("/crm/leads/new", response_class=HTMLResponse)
async def leads_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """New lead form."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Lead"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm"},
        {"label": "Leads", "href": "/crm/leads"},
        {"label": "New"},
    ])
    context["source_options"] = LEAD_SOURCE_OPTIONS
    context["qualification_options"] = LEAD_QUALIFICATION_OPTIONS
    context["form_data"] = {"type": "person"}
    context["errors"] = {}

    template = templates.get_template("modules/crm/templates/leads/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/crm/leads", response_class=HTMLResponse)
async def leads_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Create a new lead."""
    await validate_csrf(request)
    form = await request.form()

    # Extract form data
    lead_type = (form.get("type") or "person").strip()
    name = (form.get("name") or "").strip()
    first_name = (form.get("first_name") or "").strip() or None
    last_name = (form.get("last_name") or "").strip() or None
    primary_email = (form.get("primary_email") or "").strip() or None
    primary_phone = (form.get("primary_phone") or "").strip() or None
    source = (form.get("source") or "").strip() or None
    source_campaign = (form.get("source_campaign") or "").strip() or None
    qualification = (form.get("qualification") or "").strip() or None
    lead_score_str = (form.get("lead_score") or "").strip()
    notes = (form.get("notes") or "").strip() or None

    lead_score = int(lead_score_str) if lead_score_str else None

    errors: dict[str, str] = {}
    if not name:
        errors["name"] = "Name is required"

    form_data = {
        "type": lead_type,
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "primary_email": primary_email,
        "primary_phone": primary_phone,
        "source": source,
        "source_campaign": source_campaign,
        "qualification": qualification,
        "lead_score": lead_score,
        "notes": notes,
    }

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Lead"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm"},
            {"label": "Leads", "href": "/crm/leads"},
            {"label": "New"},
        ])
        context["source_options"] = LEAD_SOURCE_OPTIONS
        context["qualification_options"] = LEAD_QUALIFICATION_OPTIONS
        context["form_data"] = form_data
        context["errors"] = errors

        template = templates.get_template("modules/crm/templates/leads/pages/form.html")
        return HTMLResponse(template.render(context))

    # Create the lead
    lead_service = get_lead_service(db)
    try:
        lead_data = LeadCreateData(
            name=name,
            type=lead_type,
            first_name=first_name,
            last_name=last_name,
            primary_email=primary_email,
            primary_phone=primary_phone,
            source=source,
            source_campaign=source_campaign,
            qualification=qualification,
            lead_score=lead_score,
            notes=notes,
        )
        lead = lead_service.create_lead(lead_data)
        db.commit()

        return RedirectResponse(
            url=f"/crm/leads/{lead.party_id}",
            status_code=303,
        )
    except ValidationError as e:
        errors["form"] = str(e)
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Lead"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm"},
            {"label": "Leads", "href": "/crm/leads"},
            {"label": "New"},
        ])
        context["source_options"] = LEAD_SOURCE_OPTIONS
        context["qualification_options"] = LEAD_QUALIFICATION_OPTIONS
        context["form_data"] = form_data
        context["errors"] = errors

        template = templates.get_template("modules/crm/templates/leads/pages/form.html")
        return HTMLResponse(template.render(context))


@router.get("/crm/leads/{lead_id}", response_class=HTMLResponse)
async def lead_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    lead_id: int,
):
    """Lead detail page using LeadService."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)

    lead_service = get_lead_service(db)
    activity_service = get_activity_service(db)

    try:
        lead = lead_service.get_lead(lead_id)
    except NotFoundError:
        context["error"] = "Lead not found"
        template = templates.get_template("modules/crm/templates/leads/pages/detail.html")
        return HTMLResponse(template.render(context), status_code=404)

    # Get activities for this lead
    activity_filters = ActivityFilters(party_id=lead_id)
    activity_result = activity_service.list_activities(
        activity_filters,
        PaginationParams(limit=10),
    )

    context["lead"] = lead
    context["activities"] = activity_result.data
    context["page_title"] = f"Lead: {lead.name}"

    template = templates.get_template("modules/crm/templates/leads/pages/detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Opportunities Routes
# =============================================================================

@router.get("/crm/opportunities", response_class=HTMLResponse)
async def opportunities_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    status: Optional[str] = None,
    stage_id: Optional[int] = None,
    view: str = "list",
    page: int = Query(1, ge=1),
):
    """List opportunities using OpportunityService."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Opportunities"
    context["now"] = datetime.utcnow()

    per_page = 25
    opp_service = get_opportunity_service(db)

    # Get stages for kanban/filter
    stages = opp_service.list_stages(active_only=True)
    context["stages"] = stages

    filters = OpportunityFilters(
        search=search,
        status=status,
        stage_id=stage_id,
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    if view == "kanban":
        # For kanban, get opportunities grouped by stage
        opportunities_by_stage = {}
        for stage in stages:
            stage_filters = OpportunityFilters(stage_id=stage.id, status="open")
            stage_result = opp_service.list_opportunities(
                stage_filters,
                PaginationParams(limit=100),
            )
            opportunities_by_stage[stage.id] = stage_result.data
        context["opportunities_by_stage"] = opportunities_by_stage
        total = sum(len(opps) for opps in opportunities_by_stage.values())
    else:
        result = opp_service.list_opportunities(filters, pagination)
        context["opportunities"] = result.data
        total = result.total

    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["search"] = search or ""
    context["status_filter"] = status
    context["stage_filter"] = stage_id
    context["view"] = view

    context["status_options"] = [
        {"value": "open", "label": "Open"},
        {"value": "won", "label": "Won"},
        {"value": "lost", "label": "Lost"},
    ]

    template_name = (
        "modules/crm/templates/opportunities/pages/kanban.html"
        if view == "kanban"
        else "modules/crm/templates/opportunities/pages/list.html"
    )
    template = templates.get_template(template_name)
    return HTMLResponse(template.render(context))


@router.get("/crm/opportunities/table", response_class=HTMLResponse)
async def opportunities_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """HTMX partial - opportunities table using OpportunityService."""
    context = get_base_context(request, response, user, csrf_token)
    per_page = 25

    opp_service = get_opportunity_service(db)
    filters = OpportunityFilters(search=search, status=status)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = opp_service.list_opportunities(filters, pagination)

    context["opportunities"] = result.data
    context["total"] = result.total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (result.total + per_page - 1) // per_page

    template = templates.get_template("modules/crm/templates/opportunities/partials/opportunities_table.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/opportunities/{opp_id}", response_class=HTMLResponse)
async def opportunity_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    opp_id: int,
):
    """Opportunity detail page using OpportunityService."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)

    opp_service = get_opportunity_service(db)
    activity_service = get_activity_service(db)

    try:
        opportunity = opp_service.get_opportunity(opp_id)
    except NotFoundError:
        context["error"] = "Opportunity not found"
        template = templates.get_template("modules/crm/templates/opportunities/pages/detail.html")
        return HTMLResponse(template.render(context), status_code=404)

    # Get all stages for stage selector
    stages = opp_service.list_stages(active_only=True)

    # Get activities for this opportunity
    activity_filters = ActivityFilters(opportunity_id=opp_id)
    activity_result = activity_service.list_activities(
        activity_filters,
        PaginationParams(limit=10),
    )

    context["opportunity"] = opportunity
    context["stage"] = opportunity.stage_rel
    context["stages"] = stages
    context["party"] = opportunity.party
    context["activities"] = activity_result.data
    context["page_title"] = f"Opportunity: {opportunity.name}"

    template = templates.get_template("modules/crm/templates/opportunities/pages/detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Activities Routes
# =============================================================================

@router.get("/crm/activities", response_class=HTMLResponse)
async def activities_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    activity_type: Optional[str] = None,
    status: Optional[str] = None,
    date_filter: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """List activities using ActivityService."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Activities"
    context["now"] = datetime.utcnow()

    per_page = 25
    activity_service = get_activity_service(db)

    # Build filters
    scheduled_after = None
    scheduled_before = None
    today = date.today()

    if date_filter == "today":
        scheduled_after = datetime.combine(today, datetime.min.time())
        scheduled_before = datetime.combine(today, datetime.max.time())
    elif date_filter == "week":
        scheduled_after = datetime.combine(today, datetime.min.time())
        week_end = today + timedelta(days=7)
        scheduled_before = datetime.combine(week_end, datetime.max.time())

    filters = ActivityFilters(
        search=search,
        activity_type=activity_type,
        status=status,
        scheduled_after=scheduled_after,
        scheduled_before=scheduled_before,
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = activity_service.list_activities(filters, pagination)

    context["activities"] = result.data
    context["total"] = result.total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (result.total + per_page - 1) // per_page
    context["search"] = search or ""
    context["type_filter"] = activity_type
    context["status_filter"] = status
    context["date_filter"] = date_filter

    context["type_options"] = [
        {"value": "call", "label": "Call", "icon": "phone"},
        {"value": "meeting", "label": "Meeting", "icon": "users"},
        {"value": "email", "label": "Email", "icon": "mail"},
        {"value": "task", "label": "Task", "icon": "check-square"},
        {"value": "note", "label": "Note", "icon": "file-text"},
    ]

    context["status_options"] = [
        {"value": "scheduled", "label": "Scheduled"},
        {"value": "in_progress", "label": "In Progress"},
        {"value": "completed", "label": "Completed"},
        {"value": "cancelled", "label": "Cancelled"},
    ]

    template = templates.get_template("modules/crm/templates/activities/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/activities/table", response_class=HTMLResponse)
async def activities_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    activity_type: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """HTMX partial - activities table using ActivityService."""
    context = get_base_context(request, response, user, csrf_token)
    per_page = 25

    activity_service = get_activity_service(db)
    filters = ActivityFilters(search=search, activity_type=activity_type)
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = activity_service.list_activities(filters, pagination)

    context["activities"] = result.data
    context["total"] = result.total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (result.total + per_page - 1) // per_page

    template = templates.get_template("modules/crm/templates/activities/partials/activities_table.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/activities/{activity_id}", response_class=HTMLResponse)
async def activity_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    activity_id: int,
):
    """Activity detail page using ActivityService."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)

    activity_service = get_activity_service(db)

    try:
        activity = activity_service.get_activity(activity_id, include_relations=True)
    except NotFoundError:
        context["error"] = "Activity not found"
        template = templates.get_template("modules/crm/templates/activities/pages/detail.html")
        return HTMLResponse(template.render(context), status_code=404)

    context["activity"] = activity
    context["party"] = activity.party
    context["opportunity"] = activity.opportunity
    context["page_title"] = f"Activity: {activity.subject}"

    template = templates.get_template("modules/crm/templates/activities/pages/detail.html")
    return HTMLResponse(template.render(context))


# =============================================================================
# Campaigns Routes
# =============================================================================

@router.get("/crm/campaigns", response_class=HTMLResponse)
async def campaigns_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """List campaigns using CampaignService."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Campaigns"
    context["now"] = datetime.utcnow()

    per_page = 25
    campaign_service = get_campaign_service(db)

    # Map status filter to is_active
    is_active = None
    if status == "active":
        is_active = True
    elif status == "paused":
        is_active = False

    filters = CampaignFilters(
        search=search,
        is_active=is_active,
    )
    pagination = PaginationParams(offset=(page - 1) * per_page, limit=per_page)

    result = campaign_service.list_campaigns(filters, pagination)

    context["campaigns"] = result.data
    context["total"] = result.total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (result.total + per_page - 1) // per_page
    context["search"] = search or ""
    context["status_filter"] = status

    context["status_options"] = [
        {"value": "draft", "label": "Draft"},
        {"value": "active", "label": "Active"},
        {"value": "paused", "label": "Paused"},
        {"value": "completed", "label": "Completed"},
    ]

    template = templates.get_template("modules/crm/templates/campaigns/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/crm/campaigns/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    campaign_id: int,
):
    """Campaign detail page using CampaignService."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)

    campaign_service = get_campaign_service(db)

    try:
        campaign = campaign_service.get_campaign(campaign_id)
    except NotFoundError:
        context["error"] = "Campaign not found"
        template = templates.get_template("modules/crm/templates/campaigns/pages/detail.html")
        return HTMLResponse(template.render(context), status_code=404)

    context["campaign"] = campaign
    context["page_title"] = f"Campaign: {campaign.name}"

    template = templates.get_template("modules/crm/templates/campaigns/pages/detail.html")
    return HTMLResponse(template.render(context))
