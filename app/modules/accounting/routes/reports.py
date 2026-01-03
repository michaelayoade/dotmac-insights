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
    datetime,
)
from app.services.accounting import ReportsService
from app.services.accounting.reports_types import (
    BalanceSheetParams,
    CashFlowParams,
    IncomeStatementParams,
    FinancialRatiosParams,
)

router = APIRouter()


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
    service = ReportsService(db, user)
    as_of_date = None
    if as_of:
        try:
            as_of_date = datetime.strptime(as_of, "%Y-%m-%d")
        except ValueError:
            pass

    data = service.get_trial_balance_view(as_of_date)

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
    service = ReportsService(db, user)
    as_of_date = None
    if as_of:
        try:
            as_of_date = datetime.strptime(as_of, "%Y-%m-%d")
        except ValueError:
            pass

    data = service.get_balance_sheet(BalanceSheetParams(as_of_date=as_of_date))

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
    service = ReportsService(db, user)
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

    data = service.get_income_statement(
        IncomeStatementParams(start_date=start_date, end_date=end_date)
    )

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
    service = ReportsService(db, user)
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

    data = service.get_cash_flow(CashFlowParams(start_date=start_date, end_date=end_date))

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Reports", "href": "/accounting/reports/trial-balance"},
        {"label": "Cash Flow", "href": "/accounting/reports/cash-flow", "current": True},
    ])
    context["cash_accounts"] = data["cash_accounts"]
    context["opening_balance"] = data["opening_balance"]
    context["cash_inflows"] = data["cash_inflows"]
    context["cash_outflows"] = data["cash_outflows"]
    context["net_cash_flow"] = data["net_cash_flow"]
    context["closing_balance"] = data["closing_balance"]
    context["transactions"] = data["transactions"]
    context["start_date"] = data["start_date"]
    context["end_date"] = data["end_date"]
    context["start_param"] = start or ""
    context["end_param"] = end or ""

    template = templates.get_template("modules/accounting/templates/reports/pages/cash_flow.html")
    return HTMLResponse(template.render(context))


@router.get("/reports/financial-ratios", response_class=HTMLResponse, dependencies=[RequireAccountingRead])
async def financial_ratios_report(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
    as_of: Optional[str] = Query(None, description="As of date"),
    fiscal_year: Optional[str] = Query(None, description="Fiscal year"),
):
    """Financial ratios report."""
    service = ReportsService(db, user)
    as_of_date = None
    if as_of:
        try:
            as_of_date = datetime.strptime(as_of, "%Y-%m-%d")
        except ValueError:
            pass

    data = service.get_financial_ratios_view(
        FinancialRatiosParams(as_of_date=as_of_date, fiscal_year=fiscal_year)
    )

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["breadcrumbs"] = build_breadcrumbs([
        {"label": "Accounting", "href": "/accounting/invoices"},
        {"label": "Reports", "href": "/accounting/reports/trial-balance"},
        {"label": "Financial Ratios", "href": "/accounting/reports/financial-ratios", "current": True},
    ])
    context.update(data)
    context["as_of_param"] = as_of or ""
    context["fiscal_year_param"] = fiscal_year or ""

    template = templates.get_template("modules/accounting/templates/reports/pages/financial_ratios.html")
    return HTMLResponse(template.render(context))
