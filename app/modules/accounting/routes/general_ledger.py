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
    is_htmx_request,
    Account, GLEntry,
    func, or_, datetime, Decimal,
)

router = APIRouter()


def get_gl_stats(db) -> dict:
    """Calculate General Ledger statistics."""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_count = db.query(func.count(GLEntry.id)).filter(
        GLEntry.is_cancelled == False
    ).scalar() or 0

    this_month_count = db.query(func.count(GLEntry.id)).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= month_start
    ).scalar() or 0

    total_debit = db.query(func.sum(GLEntry.debit)).filter(
        GLEntry.is_cancelled == False
    ).scalar() or Decimal("0")

    total_credit = db.query(func.sum(GLEntry.credit)).filter(
        GLEntry.is_cancelled == False
    ).scalar() or Decimal("0")

    return {
        "total_count": total_count,
        "this_month_count": this_month_count,
        "total_debit": total_debit,
        "total_credit": total_credit,
    }


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
    # Build query
    query = db.query(GLEntry).filter(GLEntry.is_cancelled == False)

    # Search
    if q:
        query = query.filter(
            or_(
                GLEntry.voucher_no.ilike(f"%{q}%"),
                GLEntry.account.ilike(f"%{q}%"),
            )
        )

    # Filter by account
    if account_id:
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            query = query.filter(GLEntry.account == account.account_name)

    # Filter by voucher type
    if voucher_type:
        query = query.filter(GLEntry.voucher_type == voucher_type)

    # Filter by date range
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(GLEntry.posting_date >= from_date)
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d")
            query = query.filter(GLEntry.posting_date <= to_date)
        except ValueError:
            pass

    # Get total count for pagination
    total = query.count()

    # Order by posting date (newest first), then by id
    query = query.order_by(GLEntry.posting_date.desc(), GLEntry.id.desc())

    # Paginate
    entries = query.offset((page - 1) * per_page).limit(per_page).all()

    # Get accounts for filter dropdown
    accounts = db.query(Account).filter(
        Account.is_group == False,
    ).order_by(Account.account_number, Account.account_name).all()

    # Get voucher types for filter
    voucher_types = db.query(GLEntry.voucher_type).distinct().all()
    voucher_type_options = [{"value": vt[0], "label": vt[0]} for vt in voucher_types if vt[0]]

    # Get stats
    stats = get_gl_stats(db)

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
    # Build query
    query = db.query(GLEntry).filter(GLEntry.is_cancelled == False)

    # Search
    if q:
        query = query.filter(
            or_(
                GLEntry.voucher_no.ilike(f"%{q}%"),
                GLEntry.account.ilike(f"%{q}%"),
            )
        )

    # Filter by account
    if account_id:
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            query = query.filter(GLEntry.account == account.account_name)

    # Filter by voucher type
    if voucher_type:
        query = query.filter(GLEntry.voucher_type == voucher_type)

    # Filter by date range
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(GLEntry.posting_date >= from_date)
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d")
            query = query.filter(GLEntry.posting_date <= to_date)
        except ValueError:
            pass

    # Get total count for pagination
    total = query.count()

    # Order by posting date (newest first), then by id
    query = query.order_by(GLEntry.posting_date.desc(), GLEntry.id.desc())

    # Paginate
    entries = query.offset((page - 1) * per_page).limit(per_page).all()

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
