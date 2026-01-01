"""
Financial Reports routes for accounting module.
"""
from fastapi import APIRouter, Query

from ._deps import (
    Request, Response, HTMLResponse, Optional,
    SessionUser, CSRFToken, DB,
    RequireAccountingRead,
    templates,
    get_base_context, get_navigation_context, build_breadcrumbs,
    Account, GLEntry,
    func, or_, datetime, Decimal,
)

router = APIRouter()


def get_trial_balance_data(db, as_of_date: Optional[datetime] = None) -> dict:
    """Calculate trial balance data."""
    if not as_of_date:
        as_of_date = datetime.utcnow()

    # Get all accounts with their balances
    accounts_data = []

    accounts = db.query(Account).filter(
        Account.is_group == False,
    ).order_by(Account.root_type, Account.account_number, Account.account_name).all()

    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for account in accounts:
        # Get GL entries for this account up to the as_of_date
        debit_sum = db.query(func.sum(GLEntry.debit)).filter(
            GLEntry.account == account.account_name,
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= as_of_date,
        ).scalar() or Decimal("0")

        credit_sum = db.query(func.sum(GLEntry.credit)).filter(
            GLEntry.account == account.account_name,
            GLEntry.is_cancelled == False,
            GLEntry.posting_date <= as_of_date,
        ).scalar() or Decimal("0")

        balance = debit_sum - credit_sum

        # Skip zero balance accounts
        if balance == 0 and debit_sum == 0 and credit_sum == 0:
            continue

        # Determine debit/credit balance based on account type
        debit_balance = Decimal("0")
        credit_balance = Decimal("0")

        if account.root_type and account.root_type.value in ['asset', 'expense']:
            if balance >= 0:
                debit_balance = balance
            else:
                credit_balance = abs(balance)
        else:  # liability, equity, income
            if balance <= 0:
                credit_balance = abs(balance)
            else:
                debit_balance = balance

        accounts_data.append({
            "account": account,
            "debit": debit_balance,
            "credit": credit_balance,
        })

        total_debit += debit_balance
        total_credit += credit_balance

    return {
        "accounts": accounts_data,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": abs(total_debit - total_credit) < Decimal("0.01"),
        "as_of_date": as_of_date,
    }


def get_balance_sheet_data(db, as_of_date: Optional[datetime] = None) -> dict:
    """Calculate balance sheet data."""
    if not as_of_date:
        as_of_date = datetime.utcnow()

    def get_section_data(root_type: str) -> list:
        accounts = db.query(Account).filter(
            Account.is_group == False,
            Account.root_type == root_type,
        ).order_by(Account.account_number, Account.account_name).all()

        result = []
        for account in accounts:
            debit_sum = db.query(func.sum(GLEntry.debit)).filter(
                GLEntry.account == account.account_name,
                GLEntry.is_cancelled == False,
                GLEntry.posting_date <= as_of_date,
            ).scalar() or Decimal("0")

            credit_sum = db.query(func.sum(GLEntry.credit)).filter(
                GLEntry.account == account.account_name,
                GLEntry.is_cancelled == False,
                GLEntry.posting_date <= as_of_date,
            ).scalar() or Decimal("0")

            balance = debit_sum - credit_sum
            if root_type in ['liability', 'equity']:
                balance = -balance  # These normally have credit balances

            if balance != 0:
                result.append({
                    "account": account,
                    "balance": balance,
                })

        return result

    assets = get_section_data("asset")
    liabilities = get_section_data("liability")
    equity = get_section_data("equity")

    # Calculate net income (revenue - expenses) for retained earnings
    income_sum = db.query(func.sum(GLEntry.credit) - func.sum(GLEntry.debit)).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date <= as_of_date,
        GLEntry.account.in_(
            db.query(Account.account_name).filter(Account.root_type == "income")
        )
    ).scalar() or Decimal("0")

    expense_sum = db.query(func.sum(GLEntry.debit) - func.sum(GLEntry.credit)).filter(
        GLEntry.is_cancelled == False,
        GLEntry.posting_date <= as_of_date,
        GLEntry.account.in_(
            db.query(Account.account_name).filter(Account.root_type == "expense")
        )
    ).scalar() or Decimal("0")

    net_income = income_sum - expense_sum

    total_assets = sum(a["balance"] for a in assets)
    total_liabilities = sum(l["balance"] for l in liabilities)
    total_equity = sum(e["balance"] for e in equity) + net_income

    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "net_income": net_income,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "is_balanced": abs(total_assets - (total_liabilities + total_equity)) < Decimal("0.01"),
        "as_of_date": as_of_date,
    }


def get_income_statement_data(db, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> dict:
    """Calculate income statement (P&L) data."""
    now = datetime.utcnow()
    if not end_date:
        end_date = now
    if not start_date:
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    def get_section_data(root_type: str) -> list:
        accounts = db.query(Account).filter(
            Account.is_group == False,
            Account.root_type == root_type,
        ).order_by(Account.account_number, Account.account_name).all()

        result = []
        for account in accounts:
            debit_sum = db.query(func.sum(GLEntry.debit)).filter(
                GLEntry.account == account.account_name,
                GLEntry.is_cancelled == False,
                GLEntry.posting_date >= start_date,
                GLEntry.posting_date <= end_date,
            ).scalar() or Decimal("0")

            credit_sum = db.query(func.sum(GLEntry.credit)).filter(
                GLEntry.account == account.account_name,
                GLEntry.is_cancelled == False,
                GLEntry.posting_date >= start_date,
                GLEntry.posting_date <= end_date,
            ).scalar() or Decimal("0")

            if root_type == "income":
                balance = credit_sum - debit_sum
            else:  # expense
                balance = debit_sum - credit_sum

            if balance != 0:
                result.append({
                    "account": account,
                    "balance": balance,
                })

        return result

    income = get_section_data("income")
    expenses = get_section_data("expense")

    total_income = sum(i["balance"] for i in income)
    total_expenses = sum(e["balance"] for e in expenses)
    net_income = total_income - total_expenses

    return {
        "income": income,
        "expenses": expenses,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_income": net_income,
        "start_date": start_date,
        "end_date": end_date,
    }


@router.get("/reports/trial-balance", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def trial_balance_report(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    as_of: Optional[str] = Query(None, description="As of date"),
):
    """Trial Balance report."""
    as_of_date = None
    if as_of:
        try:
            as_of_date = datetime.strptime(as_of, "%Y-%m-%d")
        except ValueError:
            pass

    data = get_trial_balance_data(db, as_of_date)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Reports", "href": "/accounting/reports/trial-balance"},
        {"label": "Trial Balance", "href": "/accounting/reports/trial-balance", "current": True},
    ])
    context.update(data)
    context["as_of_param"] = as_of or ""

    template = templates.get_template("modules/accounting/templates/reports/pages/trial_balance.html")
    return HTMLResponse(template.render(context))


@router.get("/reports/balance-sheet", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def balance_sheet_report(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    as_of: Optional[str] = Query(None, description="As of date"),
):
    """Balance Sheet report."""
    as_of_date = None
    if as_of:
        try:
            as_of_date = datetime.strptime(as_of, "%Y-%m-%d")
        except ValueError:
            pass

    data = get_balance_sheet_data(db, as_of_date)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Reports", "href": "/accounting/reports/trial-balance"},
        {"label": "Balance Sheet", "href": "/accounting/reports/balance-sheet", "current": True},
    ])
    context.update(data)
    context["as_of_param"] = as_of or ""

    template = templates.get_template("modules/accounting/templates/reports/pages/balance_sheet.html")
    return HTMLResponse(template.render(context))


@router.get("/reports/income-statement", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def income_statement_report(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    start: Optional[str] = Query(None, description="Start date"),
    end: Optional[str] = Query(None, description="End date"),
):
    """Income Statement (Profit & Loss) report."""
    start_date = None
    end_date = None

    if start:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
        except ValueError:
            pass
    if end:
        try:
            end_date = datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            pass

    data = get_income_statement_data(db, start_date, end_date)

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Reports", "href": "/accounting/reports/trial-balance"},
        {"label": "Income Statement", "href": "/accounting/reports/income-statement", "current": True},
    ])
    context.update(data)
    context["start_param"] = start or ""
    context["end_param"] = end or ""

    template = templates.get_template("modules/accounting/templates/reports/pages/income_statement.html")
    return HTMLResponse(template.render(context))


@router.get("/reports/cash-flow", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def cash_flow_report(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    start: Optional[str] = Query(None, description="Start date"),
    end: Optional[str] = Query(None, description="End date"),
):
    """Cash Flow Statement report."""
    now = datetime.utcnow()
    start_date = None
    end_date = None

    if start:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
        except ValueError:
            pass
    if end:
        try:
            end_date = datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            pass

    if not end_date:
        end_date = now
    if not start_date:
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # Simplified cash flow - in a real implementation, you'd categorize accounts
    # Get cash/bank accounts
    cash_accounts = db.query(Account).filter(
        Account.is_group == False,
        Account.root_type == "asset",
        or_(
            Account.account_type.ilike("%cash%"),
            Account.account_type.ilike("%bank%"),
            Account.account_name.ilike("%cash%"),
            Account.account_name.ilike("%bank%"),
        )
    ).all()

    cash_account_names = [a.account_name for a in cash_accounts]

    # Opening cash balance
    opening_debit = db.query(func.sum(GLEntry.debit)).filter(
        GLEntry.account.in_(cash_account_names),
        GLEntry.is_cancelled == False,
        GLEntry.posting_date < start_date,
    ).scalar() or Decimal("0")

    opening_credit = db.query(func.sum(GLEntry.credit)).filter(
        GLEntry.account.in_(cash_account_names),
        GLEntry.is_cancelled == False,
        GLEntry.posting_date < start_date,
    ).scalar() or Decimal("0")

    opening_balance = opening_debit - opening_credit

    # Period cash movement
    period_debit = db.query(func.sum(GLEntry.debit)).filter(
        GLEntry.account.in_(cash_account_names),
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= start_date,
        GLEntry.posting_date <= end_date,
    ).scalar() or Decimal("0")

    period_credit = db.query(func.sum(GLEntry.credit)).filter(
        GLEntry.account.in_(cash_account_names),
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= start_date,
        GLEntry.posting_date <= end_date,
    ).scalar() or Decimal("0")

    net_cash_flow = period_debit - period_credit
    closing_balance = opening_balance + net_cash_flow

    # Get cash transactions for the period
    cash_transactions = db.query(GLEntry).filter(
        GLEntry.account.in_(cash_account_names),
        GLEntry.is_cancelled == False,
        GLEntry.posting_date >= start_date,
        GLEntry.posting_date <= end_date,
    ).order_by(GLEntry.posting_date.desc()).limit(50).all()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Reports", "href": "/accounting/reports/trial-balance"},
        {"label": "Cash Flow", "href": "/accounting/reports/cash-flow", "current": True},
    ])
    context["cash_accounts"] = cash_accounts
    context["opening_balance"] = opening_balance
    context["cash_inflows"] = period_debit
    context["cash_outflows"] = period_credit
    context["net_cash_flow"] = net_cash_flow
    context["closing_balance"] = closing_balance
    context["transactions"] = cash_transactions
    context["start_date"] = start_date
    context["end_date"] = end_date
    context["start_param"] = start or ""
    context["end_param"] = end or ""

    template = templates.get_template("modules/accounting/templates/reports/pages/cash_flow.html")
    return HTMLResponse(template.render(context))
