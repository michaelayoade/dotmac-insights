"""
Invoices module web routes.

Provides SSR pages for invoice management and credit notes.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, Depends, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import date
from decimal import Decimal

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.models.invoice import Invoice, InvoiceStatus
from app.models.credit_note import CreditNote, CreditNoteStatus
from app.models.document_lines import InvoiceLine
from app.core.security import validate_csrf, set_flash

router = APIRouter(prefix="/invoices", tags=["invoices-web"])
templates = get_template_env()

RequireInvoicesRead = Depends(require_scope("invoices:read"))
RequireInvoicesWrite = Depends(require_scope("invoices:write"))


@router.get("", response_class=HTMLResponse, dependencies=[RequireInvoicesRead])
async def invoices_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[date] = Query(None, description="Invoice date from"),
    date_to: Optional[date] = Query(None, description="Invoice date to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("invoice_date", description="Sort field"),
    dir: str = Query("desc", description="Sort direction"),
):
    """Invoices list page."""
    query = select(Invoice).options(
        selectinload(Invoice.contact),
        selectinload(Invoice.customer)
    )

    # Search
    if q:
        search = f"%{q}%"
        query = query.where(
            or_(
                Invoice.invoice_number.ilike(search),
                Invoice.contact.has(func.lower(func.coalesce(Invoice.contact.property.mapper.class_.name, '')).contains(q.lower())),
            )
        )

    # Filters
    if status:
        try:
            status_enum = InvoiceStatus(status.upper())
            query = query.where(Invoice.status == status_enum)
        except ValueError:
            pass

    if date_from:
        query = query.where(Invoice.invoice_date >= date_from)

    if date_to:
        query = query.where(Invoice.invoice_date <= date_to)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    # Sorting
    sort_column = getattr(Invoice, sort, Invoice.invoice_date)
    if dir == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    invoices = result.scalars().all()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Invoices"
    context["invoices"] = invoices
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["q"] = q or ""
    context["status_filter"] = status or ""
    context["date_from"] = date_from.isoformat() if date_from else ""
    context["date_to"] = date_to.isoformat() if date_to else ""
    context["sort"] = sort
    context["dir"] = dir

    # Status options
    context["status_options"] = [
        {"value": s.value.lower(), "label": s.value.replace("_", " ").title()}
        for s in InvoiceStatus
    ]

    if request.headers.get("HX-Request"):
        template = templates.get_template("invoices/partials/invoices_table.html")
    else:
        template = templates.get_template("invoices/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/table", response_class=HTMLResponse, dependencies=[RequireInvoicesRead])
async def invoices_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    sort: str = Query("invoice_date"),
    dir: str = Query("desc"),
):
    """Invoices table partial for HTMX."""
    return await invoices_list(
        request, response, user, csrf_token, db,
        q, status, date_from, date_to, page, per_page, sort, dir
    )


@router.get("/credit-notes", response_class=HTMLResponse, dependencies=[RequireInvoicesRead])
async def credit_notes_list(
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
    """Credit notes list page."""
    query = select(CreditNote).options(
        selectinload(CreditNote.contact),
        selectinload(CreditNote.invoice)
    )

    if q:
        search = f"%{q}%"
        query = query.where(CreditNote.credit_number.ilike(search))

    if status:
        try:
            status_enum = CreditNoteStatus(status.upper())
            query = query.where(CreditNote.status == status_enum)
        except ValueError:
            pass

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    query = query.order_by(CreditNote.issue_date.desc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = db.execute(query)
    credit_notes = result.scalars().all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Credit Notes"
    context["credit_notes"] = credit_notes
    context["total"] = total
    context["page"] = page
    context["per_page"] = per_page
    context["total_pages"] = (total + per_page - 1) // per_page
    context["q"] = q or ""
    context["status_filter"] = status or ""

    context["status_options"] = [
        {"value": s.value.lower(), "label": s.value.replace("_", " ").title()}
        for s in CreditNoteStatus
    ]

    if request.headers.get("HX-Request"):
        template = templates.get_template("invoices/partials/credit_notes_table.html")
    else:
        template = templates.get_template("invoices/pages/credit_notes.html")

    return HTMLResponse(template.render(context))


@router.get("/{invoice_id}", response_class=HTMLResponse, dependencies=[RequireInvoicesRead])
async def invoice_detail(
    invoice_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Invoice detail page."""
    query = (
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.payments),
            selectinload(Invoice.credit_notes),
            selectinload(Invoice.contact),
            selectinload(Invoice.customer),
            selectinload(Invoice.allocations),
        )
        .where(Invoice.id == invoice_id)
    )
    result = db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Invoice not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Invoice: {invoice.invoice_number or invoice.id}"
    context["invoice"] = invoice

    template = templates.get_template("invoices/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/credit-notes/{credit_note_id}", response_class=HTMLResponse, dependencies=[RequireInvoicesRead])
async def credit_note_detail(
    credit_note_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Credit note detail page."""
    query = (
        select(CreditNote)
        .options(
            selectinload(CreditNote.lines),
            selectinload(CreditNote.invoice),
            selectinload(CreditNote.contact),
        )
        .where(CreditNote.id == credit_note_id)
    )
    result = db.execute(query)
    credit_note = result.scalar_one_or_none()

    if not credit_note:
        template = templates.get_template("errors/404.html")
        context = get_base_context(request, response, user, csrf_token)
        context["message"] = "Credit note not found"
        return HTMLResponse(template.render(context), status_code=404)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = f"Credit Note: {credit_note.credit_number or credit_note.id}"
    context["credit_note"] = credit_note

    template = templates.get_template("invoices/pages/credit_note_detail.html")
    return HTMLResponse(template.render(context))


@router.post("/{invoice_id}/mark-paid", response_class=HTMLResponse, dependencies=[RequireInvoicesWrite])
async def mark_invoice_paid(
    invoice_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Quick mark invoice as paid."""
    await validate_csrf(request)

    query = select(Invoice).where(Invoice.id == invoice_id)
    result = db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        set_flash(response, "Invoice not found", "error")
        return RedirectResponse(url="/invoices", status_code=303)

    if invoice.status not in [InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]:
        set_flash(response, f"Cannot mark invoice as paid - current status: {invoice.status.value}", "error")
        return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)

    # Update invoice status
    invoice.status = InvoiceStatus.PAID
    invoice.amount_paid = invoice.total_amount
    invoice.balance = Decimal("0")
    from datetime import datetime
    invoice.paid_date = datetime.utcnow()

    db.commit()

    set_flash(response, f"Invoice {invoice.invoice_number} marked as paid", "success")
    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)
