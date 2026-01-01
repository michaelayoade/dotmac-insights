"""
CRM Routes - Contact Management with SSR + HTMX.

This module demonstrates the SSR pattern for list/detail/edit pages:
- Full page loads return complete HTML
- HTMX requests return partial HTML fragments
- Consistent URL patterns and data-testid attributes

Permission Requirements:
- crm:read - View contacts and contact details
- crm:write - Create, update, delete contacts
"""
from __future__ import annotations

from typing import Optional, Any

from fastapi import APIRouter, Request, Response, Query, HTTPException, Depends, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB, require_scope
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.contact import Contact, ContactType, ContactStatus
from app.core.security import is_htmx_request, htmx_toast, htmx_close_modal, set_flash

# Permission dependencies
RequireCRMRead = Depends(require_scope("crm:read"))
RequireCRMWrite = Depends(require_scope("crm:write"))

router = APIRouter(prefix="/crm/contacts", tags=["crm"])
templates = get_template_env()

def _form_str(form: Any, key: str, default: str = "") -> str:
    value = form.get(key, default)
    if isinstance(value, UploadFile) or value is None:
        return default
    return str(value).strip()


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


@router.get("", response_class=HTMLResponse, dependencies=[RequireCRMRead])
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


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireCRMRead])
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


@router.get("/new", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
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


@router.post("", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
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
    name = _form_str(form, "name")
    email = _form_str(form, "email")

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
        phone=_form_str(form, "phone") or None,
        contact_type=_form_str(form, "contact_type", ContactType.LEAD.value),
        status=_form_str(form, "status", ContactStatus.ACTIVE.value),
        notes=_form_str(form, "notes") or None,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    set_flash(response, f"Contact '{contact.name}' created successfully.", "success")

    # Redirect to detail page
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/crm/contacts/{contact.id}", status_code=303)


@router.get("/search", response_class=HTMLResponse, dependencies=[RequireCRMRead])
async def contacts_search(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: str = Query("", description="Search query"),
    limit: int = Query(10, ge=1, le=50),
):
    """Search contacts for HTMX typeahead.

    Returns a partial with clickable contact options for FK selection.
    """
    contacts = []
    if q and len(q) >= 2:
        search_filter = or_(
            Contact.name.ilike(f"%{q}%"),
            Contact.email.ilike(f"%{q}%"),
            Contact.phone.ilike(f"%{q}%"),
        )
        contacts = db.query(Contact).filter(search_filter).order_by(Contact.name).limit(limit).all()

    context = get_base_context(request, response, user, csrf_token)
    context["contacts"] = contacts
    context["search_query"] = q

    template = templates.get_template("modules/crm/templates/partials/search_results.html")
    return HTMLResponse(template.render(context))


@router.get("/{contact_id}", response_class=HTMLResponse, dependencies=[RequireCRMRead])
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

    # Fetch related tickets
    from app.models.unified_ticket import UnifiedTicket
    related_tickets = db.query(UnifiedTicket).filter(
        UnifiedTicket.unified_contact_id == contact_id,
        UnifiedTicket.is_deleted == False,
    ).order_by(UnifiedTicket.created_at.desc()).limit(10).all()

    ticket_stats = {
        "total": db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.unified_contact_id == contact_id,
            UnifiedTicket.is_deleted == False,
        ).scalar() or 0,
        "open": db.query(func.count(UnifiedTicket.id)).filter(
            UnifiedTicket.unified_contact_id == contact_id,
            UnifiedTicket.is_deleted == False,
            UnifiedTicket.status.in_(["open", "in_progress"]),
        ).scalar() or 0,
    }

    # Fetch related invoices (if contact has matching email)
    from app.models.invoice import Invoice
    related_invoices = []
    invoice_stats = {"total": 0, "outstanding": 0}
    if contact.email:
        from app.models.customer import Customer
        customer = db.query(Customer).filter(Customer.email == contact.email).first()
        if customer:
            related_invoices = db.query(Invoice).filter(
                Invoice.customer_id == customer.id,
            ).order_by(Invoice.created_at.desc()).limit(10).all()

            invoice_stats["total"] = db.query(func.count(Invoice.id)).filter(
                Invoice.customer_id == customer.id,
            ).scalar() or 0

            invoice_stats["outstanding"] = db.query(func.sum(Invoice.balance)).filter(
                Invoice.customer_id == customer.id,
                Invoice.balance > 0,
            ).scalar() or 0

    # Fetch related service orders (via customer)
    from app.models.field_service import ServiceOrder, ServiceOrderStatus
    related_service_orders = []
    service_order_stats = {"total": 0, "active": 0}
    if contact.email:
        from app.models.customer import Customer
        if not customer:
            customer = db.query(Customer).filter(Customer.email == contact.email).first()
        if customer:
            related_service_orders = db.query(ServiceOrder).filter(
                ServiceOrder.customer_id == customer.id,
            ).order_by(ServiceOrder.created_at.desc()).limit(10).all()

            service_order_stats["total"] = db.query(func.count(ServiceOrder.id)).filter(
                ServiceOrder.customer_id == customer.id,
            ).scalar() or 0

            active_statuses = [
                ServiceOrderStatus.SCHEDULED,
                ServiceOrderStatus.DISPATCHED,
                ServiceOrderStatus.EN_ROUTE,
                ServiceOrderStatus.ON_SITE,
                ServiceOrderStatus.IN_PROGRESS,
            ]
            service_order_stats["active"] = db.query(func.count(ServiceOrder.id)).filter(
                ServiceOrder.customer_id == customer.id,
                ServiceOrder.status.in_(active_statuses),
            ).scalar() or 0

    # Fetch related projects (via customer)
    from app.models.project import Project
    related_projects = []
    project_stats = {"total": 0, "active": 0}
    if contact.email and customer:
        related_projects = db.query(Project).filter(
            Project.customer_id == customer.id,
            Project.is_deleted == False,
        ).order_by(Project.created_at.desc()).limit(10).all()

        project_stats["total"] = db.query(func.count(Project.id)).filter(
            Project.customer_id == customer.id,
            Project.is_deleted == False,
        ).scalar() or 0

        project_stats["active"] = db.query(func.count(Project.id)).filter(
            Project.customer_id == customer.id,
            Project.is_deleted == False,
            Project.status.in_(["active", "in_progress"]),
        ).scalar() or 0

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = contact.name
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "CRM", "href": "/crm/contacts"},
        {"label": "Contacts", "href": "/crm/contacts"},
        {"label": contact.name},
    ])
    context["contact"] = contact
    context["related_tickets"] = related_tickets
    context["ticket_stats"] = ticket_stats
    context["related_invoices"] = related_invoices
    context["invoice_stats"] = invoice_stats
    context["related_service_orders"] = related_service_orders
    context["service_order_stats"] = service_order_stats
    context["related_projects"] = related_projects
    context["project_stats"] = project_stats

    template = templates.get_template("modules/crm/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{contact_id}/edit", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
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


@router.post("/{contact_id}", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
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
    name = _form_str(form, "name")
    email = _form_str(form, "email")

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
    contact.phone = _form_str(form, "phone") or None
    contact_type_value = _form_str(
        form,
        "contact_type",
        contact.contact_type.value if contact.contact_type else ContactType.LEAD.value,
    )
    status_value = _form_str(
        form,
        "status",
        contact.status.value if contact.status else ContactStatus.ACTIVE.value,
    )
    try:
        contact.contact_type = ContactType(contact_type_value)
    except ValueError:
        pass
    try:
        contact.status = ContactStatus(status_value)
    except ValueError:
        pass
    contact.notes = _form_str(form, "notes") or None
    db.commit()

    set_flash(response, f"Contact '{contact.name}' updated successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/crm/contacts/{contact.id}", status_code=303)


@router.delete("/{contact_id}", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
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


@router.patch("/{contact_id}", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def contact_patch(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    contact_id: int,
):
    """Inline update a single field on a contact.

    Used by HTMX inline edit components for quick field updates.
    Returns the updated inline component HTML.
    """
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    form = await request.form()

    # Update only provided fields
    updated_field = None
    for field_name, value in form.items():
        if field_name.startswith("_"):  # Skip CSRF and internal fields
            continue

        if isinstance(value, UploadFile):
            continue
        if hasattr(contact, field_name):
            old_value = getattr(contact, field_name)
            if field_name in ("status", "contact_type"):
                # Handle enum fields
                setattr(contact, field_name, value)
            else:
                setattr(contact, field_name, str(value).strip() if value else None)
            updated_field = field_name
            break

    if updated_field:
        db.commit()
        db.refresh(contact)
        htmx_toast(response, f"Updated {updated_field.replace('_', ' ')}", "success")

    # Return the appropriate inline component based on what was updated
    context = get_base_context(request, response, user, csrf_token)
    context["contact"] = contact
    context["status_options"] = get_status_options()
    context["type_options"] = get_type_options()

    # Return the full row for simplicity (can be optimized to return just the field)
    template = templates.get_template("modules/crm/templates/partials/contact_row.html")
    return HTMLResponse(template.render(context))


@router.get("/{contact_id}/row", response_class=HTMLResponse, dependencies=[RequireCRMRead])
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


@router.delete("/bulk", response_class=HTMLResponse, dependencies=[RequireCRMWrite])
async def contacts_bulk_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
):
    """Bulk delete contacts."""
    import json
    body = await request.body()
    data = json.loads(body) if body else {}
    ids = data.get("ids", [])

    if not ids:
        raise HTTPException(status_code=400, detail="No IDs provided")

    # Delete contacts
    deleted_count = db.query(Contact).filter(Contact.id.in_(ids)).delete(synchronize_session=False)
    db.commit()

    htmx_toast(response, f"Deleted {deleted_count} contacts", "success")
    return HTMLResponse("", headers=dict(response.headers))


@router.get("/export", dependencies=[RequireCRMRead])
async def contacts_export(
    request: Request,
    db: DB,
    ids: list[int] = Query(None, description="Contact IDs to export"),
):
    """Export contacts to CSV."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    query = db.query(Contact)
    if ids:
        query = query.filter(Contact.id.in_(ids))

    contacts = query.all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Email", "Phone", "Type", "Status", "Notes", "Created"])

    for c in contacts:
        writer.writerow([
            c.id, c.name, c.email or "", c.phone or "",
            c.contact_type, c.status, c.notes or "",
            c.created_at.isoformat() if c.created_at else ""
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts.csv"}
    )
