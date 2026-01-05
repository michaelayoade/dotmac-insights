"""
General Ledger routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException,
    datetime,
)
from app.services.accounting import LedgerService
from app.services.accounting.ledger_types import AccountFilters, GLEntryFilters
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter()

def _get_ledger_service(db: DB, user: SessionUser) -> LedgerService:
    return LedgerService(db, user)


@router.get("/general-ledger", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def general_ledger(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search by voucher number"),
    account_id: Optional[int] = Query(None, description="Filter by account"),
    voucher_type: Optional[str] = Query(None, description="Filter by voucher type"),
    date_from: Optional[str] = Query(None, description="Start date"),
    date_to: Optional[str] = Query(None, description="End date"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
):
    """General Ledger viewer page."""
    service = _get_ledger_service(db, user)

    account_name = None
    if account_id:
        try:
            account = service.get_account(account_id)
            account_name = account.account_name
        except NotFoundError:
            account_name = None

    start_date = None
    end_date = None
    if date_from:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        except ValueError:
            start_date = None
    if date_to:
        try:
            end_date = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            end_date = None

    filters = GLEntryFilters(
        search=q,
        account=account_name,
        voucher_type=voucher_type,
        start_date=start_date,
        end_date=end_date,
        is_cancelled=False,
        sort_by="posting_date",
        sort_dir="desc",
    )
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_gl_entries(filters, pagination)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entries = result.items
    total = result.total

    accounts_result = service.list_accounts(
        AccountFilters(is_group=False, include_disabled=False, sort_by="account_name"),
        PaginationParams(limit=2000, offset=0),
    )
    accounts = accounts_result.items

    voucher_type_options = [
        {"value": vt, "label": vt} for vt in service.list_voucher_types()
    ]

    stats = service.get_gl_stats()

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "General Ledger", "href": "/accounting/general-ledger", "current": True},
    ])
    context["entries"] = entries
    context["search_query"] = q or ""
    context["current_account_id"] = account_id
    context["current_voucher_type"] = voucher_type or ""
    context["date_from"] = date_from or ""
    context["date_to"] = date_to or ""
    context["accounts"] = accounts
    context["voucher_type_options"] = voucher_type_options
    context["stats"] = stats
    context["pagination"] = build_pagination_context(page, per_page, total)

    # Check if HTMX request for partial update
    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/general_ledger/partials/gl_entries_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/general_ledger/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/general-ledger/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def general_ledger_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search by voucher number"),
    account_id: Optional[int] = Query(None, description="Filter by account"),
    voucher_type: Optional[str] = Query(None, description="Filter by voucher type"),
    date_from: Optional[str] = Query(None, description="Start date"),
    date_to: Optional[str] = Query(None, description="End date"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
):
    """General Ledger table partial for HTMX."""
    service = _get_ledger_service(db, user)

    account_name = None
    if account_id:
        try:
            account = service.get_account(account_id)
            account_name = account.account_name
        except NotFoundError:
            account_name = None

    start_date = None
    end_date = None
    if date_from:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        except ValueError:
            start_date = None
    if date_to:
        try:
            end_date = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            end_date = None

    filters = GLEntryFilters(
        search=q,
        account=account_name,
        voucher_type=voucher_type,
        start_date=start_date,
        end_date=end_date,
        is_cancelled=False,
        sort_by="posting_date",
        sort_dir="desc",
    )
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_gl_entries(filters, pagination)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entries = result.items
    total = result.total

    # Build context
    context = get_base_context(request, response, user, csrf_token)
    context["entries"] = entries
    context["search_query"] = q or ""
    context["current_account_id"] = account_id
    context["current_voucher_type"] = voucher_type or ""
    context["date_from"] = date_from or ""
    context["date_to"] = date_to or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/general_ledger/partials/gl_entries_table.html")
    return HTMLResponse(template.render(context))
