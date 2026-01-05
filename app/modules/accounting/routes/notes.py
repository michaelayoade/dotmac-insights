"""
Credit/Debit Notes routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException,
)
from app.services.accounting import CreditNoteService, DebitNoteService
from app.services.accounting.credit_notes_types import CreditNoteFilters
from app.services.accounting.debit_notes_types import DebitNoteFilters
from app.services.errors import NotFoundError
from app.services.types import PaginationParams
from app.models.credit_note import CreditNoteStatus
from app.models.books_settings import DebitNoteStatus

router = APIRouter()


def _get_credit_note_service(db: DB, user: SessionUser) -> CreditNoteService:
    return CreditNoteService(db, user)


def _get_debit_note_service(db: DB, user: SessionUser) -> DebitNoteService:
    return DebitNoteService(db, user)


def _parse_credit_status(status_str: Optional[str]) -> Optional[CreditNoteStatus]:
    if not status_str:
        return None
    try:
        return CreditNoteStatus(status_str.lower())
    except ValueError:
        return None


def _parse_debit_status(status_str: Optional[str]) -> Optional[DebitNoteStatus]:
    if not status_str:
        return None
    try:
        return DebitNoteStatus(status_str.lower())
    except ValueError:
        return None


# CREDIT NOTES


@router.get("/credit-notes", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def credit_notes_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Status filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Credit notes list page."""
    service = _get_credit_note_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)

    filters = CreditNoteFilters(
        status=_parse_credit_status(status),
        search=q,
    )

    result = service.list_credit_notes(filters, pagination)
    stats = service.get_credit_note_stats()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Credit Notes", "href": None},
    ])
    context["page_title"] = "Credit Notes"
    context["notes"] = result.items
    context["total"] = result.total
    context["stats"] = stats
    context["current_search"] = q
    context["current_status"] = status
    context["status_options"] = [s.value for s in CreditNoteStatus]
    context["pagination"] = build_pagination_context(
        page=page,
        per_page=per_page,
        total=result.total,
        base_url="/accounting/credit-notes",
    )

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/notes/partials/credit_notes_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/notes/pages/credit_notes_list.html")

    return HTMLResponse(template.render(context))


@router.get("/credit-notes/{note_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def credit_note_detail(
    note_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Credit note detail page."""
    service = _get_credit_note_service(db, user)

    try:
        note = service.get_credit_note(note_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Credit note not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Credit Notes", "href": "/accounting/credit-notes"},
        {"label": note.credit_number or f"CN-{note.id}", "href": None},
    ])
    context["page_title"] = f"Credit Note: {note.credit_number}"
    context["note"] = note
    context["lines"] = getattr(note, "lines", [])

    template = templates.get_template("modules/accounting/templates/notes/pages/credit_note_detail.html")
    return HTMLResponse(template.render(context))


# DEBIT NOTES


@router.get("/debit-notes", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def debit_notes_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Status filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Debit notes list page."""
    service = _get_debit_note_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)

    filters = DebitNoteFilters(
        status=_parse_debit_status(status),
        search=q,
    )

    result = service.list_debit_notes(filters, pagination)
    stats = service.get_debit_note_stats()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Debit Notes", "href": None},
    ])
    context["page_title"] = "Debit Notes"
    context["notes"] = result.items
    context["total"] = result.total
    context["stats"] = stats
    context["current_search"] = q
    context["current_status"] = status
    context["status_options"] = [s.value for s in DebitNoteStatus]
    context["pagination"] = build_pagination_context(
        page=page,
        per_page=per_page,
        total=result.total,
        base_url="/accounting/debit-notes",
    )

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/notes/partials/debit_notes_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/notes/pages/debit_notes_list.html")

    return HTMLResponse(template.render(context))


@router.get("/debit-notes/{note_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def debit_note_detail(
    note_id: int,
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Debit note detail page."""
    service = _get_debit_note_service(db, user)

    try:
        note = service.get_debit_note(note_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Debit note not found")

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting"},
        {"label": "Debit Notes", "href": "/accounting/debit-notes"},
        {"label": note.debit_note_number or f"DN-{note.id}", "href": None},
    ])
    context["page_title"] = f"Debit Note: {note.debit_note_number}"
    context["note"] = note
    context["lines"] = getattr(note, "lines", [])

    template = templates.get_template("modules/accounting/templates/notes/pages/debit_note_detail.html")
    return HTMLResponse(template.render(context))
