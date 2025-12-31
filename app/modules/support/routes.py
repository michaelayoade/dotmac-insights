"""
Support Routes - Ticket Management with SSR + HTMX.

This module provides SSR pages for support ticket management:
- Ticket list with filtering/search
- Ticket detail with conversation view
- Create/edit ticket forms
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request, Response, Query, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload

from app.web.dependencies import SessionUser, CSRFToken, CSRFProtect, DB
from app.web.context import (
    get_base_context,
    get_navigation_context,
    build_breadcrumbs,
    build_pagination_context,
)
from app.templates.environment import get_template_env
from app.models.unified_ticket import (
    UnifiedTicket,
    TicketStatus,
    TicketPriority,
    TicketType,
    TicketChannel,
    TicketSource,
)
from app.core.security import is_htmx_request, htmx_toast, set_flash

router = APIRouter(prefix="/support/tickets", tags=["support"])
templates = get_template_env()


def get_status_options():
    """Get status options for select dropdown."""
    return [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in TicketStatus
    ]


def get_priority_options():
    """Get priority options for select dropdown."""
    return [
        {"value": p.value, "label": p.value.title()}
        for p in TicketPriority
    ]


def get_type_options():
    """Get type options for select dropdown."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in TicketType
    ]


def get_channel_options():
    """Get channel options for select dropdown."""
    return [
        {"value": c.value, "label": c.value.replace("_", " ").title()}
        for c in TicketChannel
    ]


@router.get("", response_class=HTMLResponse)
async def tickets_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    assigned: Optional[str] = Query(None, description="Filter by assignment"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Ticket list page.

    Returns full page for normal requests, table partial for HTMX requests.
    """
    # Build query
    query = db.query(UnifiedTicket).filter(UnifiedTicket.is_deleted == False)

    # Search
    if q:
        search_filter = or_(
            UnifiedTicket.subject.ilike(f"%{q}%"),
            UnifiedTicket.ticket_number.ilike(f"%{q}%"),
            UnifiedTicket.contact_name.ilike(f"%{q}%"),
            UnifiedTicket.contact_email.ilike(f"%{q}%"),
        )
        query = query.filter(search_filter)

    # Filters
    if status:
        query = query.filter(UnifiedTicket.status == status)
    if priority:
        query = query.filter(UnifiedTicket.priority == priority)
    if assigned == "me":
        # Would need to look up current user's employee ID
        pass
    elif assigned == "unassigned":
        query = query.filter(UnifiedTicket.assigned_to_id.is_(None))

    # Count total
    total = query.count()

    # Sort
    sort_column = getattr(UnifiedTicket, sort, UnifiedTicket.created_at)
    if dir == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Paginate
    offset = (page - 1) * per_page
    tickets = query.offset(offset).limit(per_page).all()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["tickets"] = tickets
    context["search_query"] = q or ""
    context["current_status"] = status
    context["current_priority"] = priority
    context["current_assigned"] = assigned
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["sort_key"] = sort
    context["sort_dir"] = dir
    context["pagination"] = build_pagination_context(page, per_page, total)

    # HTMX partial or full page
    if is_htmx_request(request):
        template = templates.get_template("modules/support/templates/partials/tickets_table.html")
        return HTMLResponse(template.render(context))

    # Full page
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Support Tickets"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/tickets"},
        {"label": "Tickets"},
    ])

    template = templates.get_template("modules/support/templates/pages/list.html")
    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse)
async def tickets_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("created_at"),
    dir: str = Query("desc"),
):
    """Ticket table partial for HTMX updates."""
    return await tickets_list(
        request, response, user, csrf_token, db,
        q, status, priority, assigned, page, per_page, sort, dir
    )


@router.get("/new", response_class=HTMLResponse)
async def ticket_new(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """New ticket form page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "New Ticket"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/tickets"},
        {"label": "Tickets", "href": "/support/tickets"},
        {"label": "New Ticket"},
    ])
    context["ticket"] = None
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["type_options"] = get_type_options()
    context["channel_options"] = get_channel_options()
    context["errors"] = {}

    template = templates.get_template("modules/support/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("", response_class=HTMLResponse)
async def ticket_create(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
):
    """Create a new ticket."""
    form = await request.form()

    # Basic validation
    errors = {}
    subject = form.get("subject", "").strip()
    description = form.get("description", "").strip()

    if not subject:
        errors["subject"] = "Subject is required"
    if len(subject) > 500:
        errors["subject"] = "Subject must be 500 characters or less"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = "New Ticket"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Support", "href": "/support/tickets"},
            {"label": "Tickets", "href": "/support/tickets"},
            {"label": "New Ticket"},
        ])
        context["ticket"] = None
        context["status_options"] = get_status_options()
        context["priority_options"] = get_priority_options()
        context["type_options"] = get_type_options()
        context["channel_options"] = get_channel_options()
        context["errors"] = errors
        context["form_data"] = dict(form)

        template = templates.get_template("modules/support/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Create ticket
    ticket = UnifiedTicket(
        subject=subject,
        description=description or None,
        ticket_type=TicketType(form.get("ticket_type", TicketType.SUPPORT.value)),
        priority=TicketPriority(form.get("priority", TicketPriority.MEDIUM.value)),
        status=TicketStatus.OPEN,
        source=TicketSource.INTERNAL,
        channel=TicketChannel(form.get("channel")) if form.get("channel") else None,
        contact_name=form.get("contact_name", "").strip() or None,
        contact_email=form.get("contact_email", "").strip() or None,
        contact_phone=form.get("contact_phone", "").strip() or None,
    )

    # Generate ticket number
    max_num = db.query(func.max(UnifiedTicket.id)).scalar() or 0
    ticket.ticket_number = f"TKT-{max_num + 1:06d}"

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    set_flash(response, f"Ticket '{ticket.ticket_number}' created successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/support/tickets/{ticket.id}", status_code=303)


@router.get("/{ticket_id}", response_class=HTMLResponse)
async def ticket_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    ticket_id: int,
):
    """Ticket detail page."""
    ticket = db.query(UnifiedTicket).filter(
        UnifiedTicket.id == ticket_id,
        UnifiedTicket.is_deleted == False,
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Ticket {ticket.ticket_number}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/tickets"},
        {"label": "Tickets", "href": "/support/tickets"},
        {"label": ticket.ticket_number or f"#{ticket.id}"},
    ])
    context["ticket"] = ticket
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()

    template = templates.get_template("modules/support/templates/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/{ticket_id}/edit", response_class=HTMLResponse)
async def ticket_edit(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    ticket_id: int,
):
    """Ticket edit form page."""
    ticket = db.query(UnifiedTicket).filter(
        UnifiedTicket.id == ticket_id,
        UnifiedTicket.is_deleted == False,
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Edit Ticket {ticket.ticket_number}"
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Support", "href": "/support/tickets"},
        {"label": "Tickets", "href": "/support/tickets"},
        {"label": ticket.ticket_number, "href": f"/support/tickets/{ticket.id}"},
        {"label": "Edit"},
    ])
    context["ticket"] = ticket
    context["status_options"] = get_status_options()
    context["priority_options"] = get_priority_options()
    context["type_options"] = get_type_options()
    context["channel_options"] = get_channel_options()
    context["errors"] = {}

    template = templates.get_template("modules/support/templates/pages/form.html")
    return HTMLResponse(template.render(context))


@router.post("/{ticket_id}", response_class=HTMLResponse)
async def ticket_update(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    ticket_id: int,
):
    """Update a ticket."""
    ticket = db.query(UnifiedTicket).filter(
        UnifiedTicket.id == ticket_id,
        UnifiedTicket.is_deleted == False,
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    form = await request.form()

    # Basic validation
    errors = {}
    subject = form.get("subject", "").strip()

    if not subject:
        errors["subject"] = "Subject is required"

    if errors:
        context = get_base_context(request, response, user, csrf_token)
        context["navigation"] = get_navigation_context(user)
        context["page_title"] = f"Edit Ticket {ticket.ticket_number}"
        context["breadcrumbs"] = build_breadcrumbs([
            {"label": "Support", "href": "/support/tickets"},
            {"label": "Tickets", "href": "/support/tickets"},
            {"label": ticket.ticket_number, "href": f"/support/tickets/{ticket.id}"},
            {"label": "Edit"},
        ])
        context["ticket"] = ticket
        context["status_options"] = get_status_options()
        context["priority_options"] = get_priority_options()
        context["type_options"] = get_type_options()
        context["channel_options"] = get_channel_options()
        context["errors"] = errors

        template = templates.get_template("modules/support/templates/pages/form.html")
        return HTMLResponse(template.render(context), status_code=422)

    # Update ticket
    ticket.subject = subject
    ticket.description = form.get("description", "").strip() or None
    ticket.ticket_type = TicketType(form.get("ticket_type", ticket.ticket_type.value))
    ticket.priority = TicketPriority(form.get("priority", ticket.priority.value))
    ticket.status = TicketStatus(form.get("status", ticket.status.value))
    ticket.channel = TicketChannel(form.get("channel")) if form.get("channel") else ticket.channel
    ticket.contact_name = form.get("contact_name", "").strip() or None
    ticket.contact_email = form.get("contact_email", "").strip() or None
    ticket.contact_phone = form.get("contact_phone", "").strip() or None
    ticket.resolution = form.get("resolution", "").strip() or None

    db.commit()

    set_flash(response, f"Ticket '{ticket.ticket_number}' updated successfully.", "success")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/support/tickets/{ticket.id}", status_code=303)


@router.delete("/{ticket_id}", response_class=HTMLResponse)
async def ticket_delete(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    ticket_id: int,
):
    """Delete a ticket (soft delete)."""
    ticket = db.query(UnifiedTicket).filter(
        UnifiedTicket.id == ticket_id,
        UnifiedTicket.is_deleted == False,
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_number = ticket.ticket_number
    ticket.soft_delete()
    db.commit()

    # For HTMX, return empty response with toast trigger
    if is_htmx_request(request):
        htmx_toast(response, f"Ticket '{ticket_number}' deleted.", "success")
        return HTMLResponse("", headers=dict(response.headers))

    set_flash(response, f"Ticket '{ticket_number}' deleted.", "success")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/support/tickets", status_code=303)


@router.post("/{ticket_id}/status", response_class=HTMLResponse)
async def ticket_update_status(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf: CSRFProtect,
    db: DB,
    ticket_id: int,
):
    """Quick status update via HTMX."""
    ticket = db.query(UnifiedTicket).filter(
        UnifiedTicket.id == ticket_id,
        UnifiedTicket.is_deleted == False,
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    form = await request.form()
    new_status = form.get("status")

    if new_status:
        ticket.status = TicketStatus(new_status)
        db.commit()

        htmx_toast(response, f"Status updated to {new_status.replace('_', ' ').title()}", "success")

    # Return updated ticket row
    context = get_base_context(request, response, user, None)
    context["ticket"] = ticket

    template = templates.get_template("modules/support/templates/partials/ticket_row.html")
    return HTMLResponse(template.render(context), headers=dict(response.headers))


@router.get("/{ticket_id}/row", response_class=HTMLResponse)
async def ticket_row(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    ticket_id: int,
):
    """Single ticket row partial for HTMX updates."""
    ticket = db.query(UnifiedTicket).filter(
        UnifiedTicket.id == ticket_id,
        UnifiedTicket.is_deleted == False,
    ).first()

    if not ticket:
        return HTMLResponse("", status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["ticket"] = ticket

    template = templates.get_template("modules/support/templates/partials/ticket_row.html")
    return HTMLResponse(template.render(context))
