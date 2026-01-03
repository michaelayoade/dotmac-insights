"""
Bank Accounts routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, RedirectResponse, Optional,
    SessionUser, CSRFToken, CSRFProtect, DB,
    RequireAccountingRead, RequireAccountingWrite,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs, build_pagination_context,
    is_htmx_request, HTTPException, set_flash,
    BankTransactionStatus,
)
from app.services.accounting import BankingService
from app.services.bank_reconciliation import BankReconciliationService
from app.services.accounting.banking_types import BankTransactionFilters
from app.services.errors import NotFoundError, ValidationError
from app.services.types import PaginationParams

router = APIRouter()


def _get_banking_service(db: DB, user: SessionUser) -> BankingService:
    return BankingService(db, user)


@router.get("/bank-accounts", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def bank_accounts_list(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Bank accounts list page."""
    service = _get_banking_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_bank_accounts_paginated(
            search=q,
            include_disabled=False,
            pagination=pagination,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    accounts = result.items
    total = result.total
    stats = service.get_bank_account_stats()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Bank Accounts", "href": "/accounting/bank-accounts", "current": True},
    ])
    context["accounts"] = accounts
    context["search_query"] = q or ""
    context["stats"] = stats
    context["pagination"] = build_pagination_context(page, per_page, total)

    if is_htmx_request(request):
        template = templates.get_template("modules/accounting/templates/bank_accounts/partials/bank_accounts_table.html")
    else:
        template = templates.get_template("modules/accounting/templates/bank_accounts/pages/list.html")

    return HTMLResponse(template.render(context))


@router.get("/bank-accounts/table", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def bank_accounts_table(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    q: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
):
    """Bank accounts table partial for HTMX."""
    service = _get_banking_service(db, user)
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        result = service.list_bank_accounts_paginated(
            search=q,
            include_disabled=False,
            pagination=pagination,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    accounts = result.items
    total = result.total

    context = get_base_context(request, response, user, csrf_token)
    context["accounts"] = accounts
    context["search_query"] = q or ""
    context["pagination"] = build_pagination_context(page, per_page, total)

    template = templates.get_template("modules/accounting/templates/bank_accounts/partials/bank_accounts_table.html")
    return HTMLResponse(template.render(context))


@router.get("/bank-accounts/{account_id}", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def bank_account_detail(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    account_id: int,
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=100),
):
    """Bank account detail page with transactions."""
    service = _get_banking_service(db, user)
    try:
        account = service.get_bank_account(account_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Bank account not found") from exc

    status_value = None
    if status:
        try:
            status_value = BankTransactionStatus(status).value
        except ValueError:
            status_value = None

    filters = BankTransactionFilters(
        bank_account_id=account_id,
        status=status_value,
        sort_by="date",
        sort_dir="desc",
    )
    pagination = PaginationParams(limit=per_page, offset=(page - 1) * per_page)
    try:
        txn_result = service.list_transactions(filters, pagination)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    transactions = txn_result.items
    total_txns = txn_result.total

    balance_info = service.get_bank_account_balance_summary(account)
    total_deposits = balance_info["total_deposits"]
    total_withdrawals = balance_info["total_withdrawals"]
    balance = balance_info["balance"]

    # Status options
    status_options = [{"value": s.value, "label": s.value.replace("_", " ").title()} for s in BankTransactionStatus]

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Bank Accounts", "href": "/accounting/bank-accounts"},
        {"label": account.account_name, "href": f"/accounting/bank-accounts/{account_id}", "current": True},
    ])
    context["account"] = account
    context["transactions"] = transactions
    context["total_deposits"] = total_deposits
    context["total_withdrawals"] = total_withdrawals
    context["balance"] = balance
    context["current_status"] = status or ""
    context["status_options"] = status_options
    context["pagination"] = build_pagination_context(page, per_page, total_txns)

    template = templates.get_template("modules/accounting/templates/bank_accounts/pages/detail.html")
    return HTMLResponse(template.render(context))


@router.get("/bank-accounts/{account_id}/reconcile", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def bank_reconciliation_page(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    account_id: int,
):
    """Bank reconciliation interface."""
    service = _get_banking_service(db, user)
    try:
        account = service.get_bank_account(account_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Bank account not found") from exc

    unreconciled_txns = service.list_unreconciled_transactions(account, limit=100)

    recon_service = BankReconciliationService(db)
    reconciliations = recon_service.list_recent_reconciliations(
        account.account_name,
        limit=10,
    )

    # Calculate totals
    unreconciled_deposits = sum(t.deposit or Decimal("0") for t in unreconciled_txns)
    unreconciled_withdrawals = sum(t.withdrawal or Decimal("0") for t in unreconciled_txns)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Bank Accounts", "href": "/accounting/bank-accounts"},
        {"label": account.account_name, "href": f"/accounting/bank-accounts/{account_id}"},
        {"label": "Reconcile", "href": f"/accounting/bank-accounts/{account_id}/reconcile", "current": True},
    ])
    context["account"] = account
    context["unreconciled_txns"] = unreconciled_txns
    context["reconciliations"] = reconciliations
    context["unreconciled_deposits"] = unreconciled_deposits
    context["unreconciled_withdrawals"] = unreconciled_withdrawals

    template = templates.get_template("modules/accounting/templates/bank_accounts/pages/reconcile.html")
    return HTMLResponse(template.render(context))


@router.post("/bank-accounts/{account_id}/reconcile", response_class=HTMLResponse, dependencies=[RequireAccountingWrite])
async def bank_reconciliation_mark(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    csrf: CSRFProtect,
    db: DB,
    account_id: int,
):
    """Mark selected transactions as reconciled."""
    service = _get_banking_service(db, user)
    try:
        service.get_bank_account(account_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Bank account not found") from exc

    form = await request.form()
    txn_ids = form.getlist("transaction_ids")

    if not txn_ids:
        set_flash(response, "No transactions selected.", "warning")
        return RedirectResponse(url=f"/accounting/bank-accounts/{account_id}/reconcile", status_code=303)

    # Mark transactions as reconciled
    parsed_ids = []
    for txn_id in txn_ids:
        if not isinstance(txn_id, str):
            continue
        try:
            parsed_ids.append(int(txn_id))
        except ValueError:
            continue

    count = service.mark_transactions_reconciled(parsed_ids)
    db.commit()
    set_flash(response, f"Marked {count} transaction(s) as reconciled.", "success")
    return RedirectResponse(url=f"/accounting/bank-accounts/{account_id}/reconcile", status_code=303)
