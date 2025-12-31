"""
CRM Routes - Contact Management with SSR + HTMX.

This module demonstrates the SSR pattern for list/detail/edit pages:
- Full page loads return complete HTML
- HTMX requests return partial HTML fragments
- Consistent URL patterns and data-testid attributes
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request, Response, Query, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.contact import Contact, ContactType, ContactStatus
from app.core.security import is_htmx_request, htmx_toast, htmx_close_modal, set_flash

router = APIRouter(prefix="/crm/contacts", tags=["crm"])
templates = get_template_env()


def get_status_options():
    """Get status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in ContactStatus
    ]


def get_type_options():
    """Get type options for select dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in ContactType
    ]


@router.get("", response_class=HTMLResponse)
async def contacts_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    type: Optional[str] = Query(None, description="Filter by type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("name", description="Sort field"),
    dir: str = Query("asc", description="Sort direction"),
):
    """Contact list page.

    Returns full page for normal requests, table partial for HTMX requests.
    """
    # Build query
    query = db.query(Contact)

    # Search
    if q:
        search_filter = or_(
            Contact.name.ilike(f"%{q}%"),
            Contact.email.ilike(f"%{q}%"),
            Contact.phone.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(Contact.status == status)
    if type:
        query = query.filter(Contact.contact_type == type)

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(Contact, sort, Contact.name)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    contacts = query.offset(offset).limit(per_page).all()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["contacts"] = contacts
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_type"] = type
    context["status_options"] = get_status_options()
    context["type_options"] = get_type_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/crm/templates/partials/contacts_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Contacts"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Contacts"},
    ])

    template = templates.get_template("modules/crm/templates/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse)
async def contacts_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("name"),
    dir: str = Query("asc"),
):
    """Contact table partial for HTMX updates."""
    # Reuse the list logic but always return partial
    return await contacts_list(
        request, response, user, csrf_token, db,
        q, status, type, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse)
async def contact_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """New contact form page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Contact"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Contacts", "href": "/crm/contacts"},
        {"label": "New Contact"},
    ])
    context["contact"] = None
    context["status_options"] = get_status_options()
    context["type_options"] = get_type_options()
    context["errors"] = {}

    template = templates.get_template("modules/crm/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse)
async def contact_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new contact."""
    form = await request.form()

    # Basic validation
    errors = {}
    name = form.get("name", "").strip()
    email = form.get("email", "").strip()

    if not name:
        errors["name"] = "Name is required"
    if email and "@" not in email:
        errors["email"] = "Invalid email address"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Contact"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm/contacts"},
            {"label": "Contacts", "href": "/crm/contacts"},
            {"label": "New Contact"},
        ])
        context["contact"] = None
        context["status_options"] = get_status_options()
        context["type_options"] = get_type_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/crm/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Create contact
    contact = Contact(
        name=name,
        email=email or None,
        phone=form.get("phone", "").strip() or None,
        contact_type=form.get("contact_type", ContactType.LEAD.value),
        status=form.get("status", ContactStatus.ACTIVE.value),
        notes=form.get("notes", "").strip() or None,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    set_flash(response, f"Contact '{contact.name}' created successfully.", "success")

    # Redirect to detail page
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/crm/contacts/{contact.id}", status_code=303)


@router.get("/{contact_id}", response_class=HTMLResponse)
async def contact_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    contact_id: int,
):
    """Contact detail page."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = contact.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Contacts", "href": "/crm/contacts"},
        {"label": contact.name},
    ])
    context["contact"] = contact

    template = templates.get_template("modules/crm/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{contact_id}/edit", response_class=HTMLResponse)
async def contact_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    contact_id: int,
):
    """Contact edit form page."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit {contact.name}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Contacts", "href": "/crm/contacts"},
        {"label": contact.name, "href": f"/crm/contacts/{contact.id}"},
        {"label": "Edit"},
    ])
    context["contact"] = contact
    context["status_options"] = get_status_options()
    context["type_options"] = get_type_options()
    context["errors"] = {}

    template = templates.get_template("modules/crm/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{contact_id}", response_class=HTMLResponse)
async def contact_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    contact_id: int,
):
    """Update a contact."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    form = await request.form()

    # Basic validation
    errors = {}
    name = form.get("name", "").strip()
    email = form.get("email", "").strip()

    if not name:
        errors["name"] = "Name is required"
    if email and "@" not in email:
        errors["email"] = "Invalid email address"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit {contact.name}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "CRM", "href": "/crm/contacts"},
            {"label": "Contacts", "href": "/crm/contacts"},
            {"label": contact.name, "href": f"/crm/contacts/{contact.id}"},
            {"label": "Edit"},
        ])
        context["contact"] = contact
        context["status_options"] = get_status_options()
        context["type_options"] = get_type_options()
        context["errors"] = errors

        template = templates.get_template("modules/crm/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Update contact
    contact.name = name
    contact.email = email or None
    contact.phone = form.get("phone", "").strip() or None
    contact.contact_type = form.get("contact_type", contact.contact_type)
    contact.status = form.get("status", contact.status)
    contact.notes = form.get("notes", "").strip() or None
    db.commit()

    set_flash(response, f"Contact '{contact.name}' updated successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/crm/contacts/{contact.id}", status_code=303)


@router.delete("/{contact_id}", response_class=HTMLResponse)
async def contact_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    contact_id: int,
):
    """Delete a contact."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    name = contact.name
    db.delete(contact)
    db.commit()

    # For HTMX, return empty response with toast trigger
    if is_htmx_request(request):
        htmx_toast(response, f"Contact '{name}' deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Contact '{name}' deleted.", "success")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/crm/contacts", status_code=303)


@router.get("/{contact_id}/row", response_class=HTMLResponse)
async def contact_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    contact_id: int,
):
    """Single contact row partial for HTMX updates."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
    ).first()

    if not contact:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["contact"] = contact

    template = templates.get_template("modules/crm/templates/partials/contact_row.html")
    return HTMLResponse(template.render(context))
