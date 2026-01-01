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
    BankAccount, BankTransaction, BankTransactionStatus, BankReconciliation,
    func, or_, datetime, Decimal,
)

router = APIRouter()


def get_bank_account_stats(db) -> dict:
    """Calculate bank account statistics."""
    total_count = db.query(func.count(BankAccount.id)).filter(
        BankAccount.disabled == False
    ).scalar() or 0

    # Transaction counts
    unreconciled = db.query(func.count(BankTransaction.id)).filter(
        BankTransaction.status == BankTransactionStatus.UNRECONCILED
    ).scalar() or 0

    pending = db.query(func.count(BankTransaction.id)).filter(
        BankTransaction.status == BankTransactionStatus.PENDING
    ).scalar() or 0

    return {
        "total_accounts": total_count,
        "unreconciled_txns": unreconciled,
        "pending_txns": pending,
    }


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
    query = db.query(BankAccount).filter(BankAccount.disabled == False)

    if q:
        query = query.filter(
            or_(
                BankAccount.account_name.ilike(f"%{q}%"),
                BankAccount.bank.ilike(f"%{q}%"),
                BankAccount.bank_account_no.ilike(f"%{q}%"),
            )
        )

    total = query.count()
    query = query.order_by(BankAccount.account_name)
    accounts = query.offset((page - 1) * per_page).limit(per_page).all()

    stats = get_bank_account_stats(db)

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
    query = db.query(BankAccount).filter(BankAccount.disabled == False)

    if q:
        query = query.filter(
            or_(
                BankAccount.account_name.ilike(f"%{q}%"),
                BankAccount.bank.ilike(f"%{q}%"),
                BankAccount.bank_account_no.ilike(f"%{q}%"),
            )
        )

    total = query.count()
    query = query.order_by(BankAccount.account_name)
    accounts = query.offset((page - 1) * per_page).limit(per_page).all()

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
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    # Get transactions
    txn_query = db.query(BankTransaction).filter(
        or_(
            BankTransaction.bank_account_id == account_id,
            BankTransaction.bank_account == account.account_name,
        )
    )

    if status:
        try:
            txn_status = BankTransactionStatus(status)
            txn_query = txn_query.filter(BankTransaction.status == txn_status)
        except ValueError:
            pass

    total_txns = txn_query.count()
    txn_query = txn_query.order_by(BankTransaction.date.desc())
    transactions = txn_query.offset((page - 1) * per_page).limit(per_page).all()

    # Calculate balance
    total_deposits = db.query(func.sum(BankTransaction.deposit)).filter(
        or_(
            BankTransaction.bank_account_id == account_id,
            BankTransaction.bank_account == account.account_name,
        )
    ).scalar() or Decimal("0")

    total_withdrawals = db.query(func.sum(BankTransaction.withdrawal)).filter(
        or_(
            BankTransaction.bank_account_id == account_id,
            BankTransaction.bank_account == account.account_name,
        )
    ).scalar() or Decimal("0")

    balance = total_deposits - total_withdrawals

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
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    # Get unreconciled transactions
    unreconciled_txns = db.query(BankTransaction).filter(
        or_(
            BankTransaction.bank_account_id == account_id,
            BankTransaction.bank_account == account.account_name,
        ),
        BankTransaction.status.in_([BankTransactionStatus.UNRECONCILED, BankTransactionStatus.PENDING])
    ).order_by(BankTransaction.date.desc()).limit(100).all()

    # Get recent reconciliations
    reconciliations = db.query(BankReconciliation).filter(
        BankReconciliation.bank_account == account.account_name
    ).order_by(BankReconciliation.to_date.desc()).limit(10).all()

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
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    form = await request.form()
    txn_ids = form.getlist("transaction_ids")

    if not txn_ids:
        set_flash(response, "No transactions selected.", "warning")
        return RedirectResponse(url=f"/accounting/bank-accounts/{account_id}/reconcile", status_code=303)

    # Mark transactions as reconciled
    count = 0
    for txn_id in txn_ids:
        if not isinstance(txn_id, str):
            continue
        try:
            txn = db.query(BankTransaction).filter(BankTransaction.id == int(txn_id)).first()
            if txn:
                txn.status = BankTransactionStatus.RECONCILED
                count += 1
        except ValueError:
            pass

    db.commit()
    set_flash(response, f"Marked {count} transaction(s) as reconciled.", "success")
    return RedirectResponse(url=f"/accounting/bank-accounts/{account_id}/reconcile", status_code=303)
