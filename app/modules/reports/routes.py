"""
Reports module web routes.

Provides SSR pages for financial reports dashboard and individual reports.
Leverages existing API endpoints for data.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, Depends, Query
from fastapi.responses import HTMLResponse
from typing import Optional
from datetime import date, timedelta
from decimal import Decimal
import httpx

from app.web.dependencies import SessionUser, CSRFToken, DB, require_scope
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env
from app.config import settings

router = APIRouter(prefix="/reports", tags=["reports-web"])
templates = get_template_env()

RequireReportsRead = Depends(require_scope("reports:read"))


def get_default_dates() -> tuple[date, date]:
    """Get default date range (current month)."""
    today = date.today()
    start_of_month = today.replace(day=1)
    return start_of_month, today


def get_fiscal_year_dates() -> tuple[date, date]:
    """Get current fiscal year dates (assumes Jan 1 start)."""
    today = date.today()
    start_of_year = date(today.year, 1, 1)
    return start_of_year, today


@router.get("", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def reports_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
):
    """Reports dashboard/hub page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Reports"

    # Define available reports
    context["financial_reports"] = [
        {
            "name": "Trial Balance",
            "description": "Account balances at a point in time",
            "url": "/reports/trial-balance",
            "icon": "scale",
        },
        {
            "name": "Balance Sheet",
            "description": "Assets, liabilities, and equity",
            "url": "/reports/balance-sheet",
            "icon": "chart-pie",
        },
        {
            "name": "Income Statement",
            "description": "Revenue and expenses (P&L)",
            "url": "/reports/income-statement",
            "icon": "trending-up",
        },
        {
            "name": "Cash Flow",
            "description": "Cash movements by activity",
            "url": "/reports/cash-flow",
            "icon": "currency-dollar",
        },
        {
            "name": "General Ledger",
            "description": "All transactions by account",
            "url": "/reports/general-ledger",
            "icon": "book-open",
        },
    ]

    context["ar_reports"] = [
        {
            "name": "Receivables Aging",
            "description": "Outstanding customer invoices by age",
            "url": "/reports/receivables-aging",
            "icon": "clock",
        },
        {
            "name": "Customer Balances",
            "description": "Balances by customer",
            "url": "/reports/customer-balances",
            "icon": "users",
        },
    ]

    context["ap_reports"] = [
        {
            "name": "Payables Aging",
            "description": "Outstanding supplier bills by age",
            "url": "/reports/payables-aging",
            "icon": "clock",
        },
        {
            "name": "Supplier Balances",
            "description": "Balances by supplier",
            "url": "/reports/supplier-balances",
            "icon": "truck",
        },
    ]

    context["analytics_reports"] = [
        {
            "name": "Financial Ratios",
            "description": "Key financial metrics and ratios",
            "url": "/reports/financial-ratios",
            "icon": "calculator",
        },
        {
            "name": "Revenue Analysis",
            "description": "Revenue trends and breakdown",
            "url": "/reports/revenue-analysis",
            "icon": "chart-bar",
        },
    ]

    template = templates.get_template("reports/pages/dashboard.html")
    return HTMLResponse(template.render(context))


@router.get("/trial-balance", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def trial_balance(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    as_of: Optional[date] = Query(None, description="As of date"),
):
    """Trial Balance report page."""
    if not as_of:
        as_of = date.today()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Trial Balance"
    context["as_of"] = as_of.isoformat()
    context["report_type"] = "trial-balance"

    template = templates.get_template("reports/pages/trial_balance.html")
    return HTMLResponse(template.render(context))


@router.get("/balance-sheet", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def balance_sheet(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    as_of: Optional[date] = Query(None, description="As of date"),
    comparative: bool = Query(False, description="Show comparative period"),
):
    """Balance Sheet report page."""
    if not as_of:
        as_of = date.today()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Balance Sheet"
    context["as_of"] = as_of.isoformat()
    context["comparative"] = comparative
    context["report_type"] = "balance-sheet"

    template = templates.get_template("reports/pages/balance_sheet.html")
    return HTMLResponse(template.render(context))


@router.get("/income-statement", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def income_statement(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    comparative: bool = Query(False, description="Show comparative period"),
):
    """Income Statement (P&L) report page."""
    if not start_date or not end_date:
        start_date, end_date = get_fiscal_year_dates()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Income Statement"
    context["start_date"] = start_date.isoformat()
    context["end_date"] = end_date.isoformat()
    context["comparative"] = comparative
    context["report_type"] = "income-statement"

    template = templates.get_template("reports/pages/income_statement.html")
    return HTMLResponse(template.render(context))


@router.get("/cash-flow", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def cash_flow(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
):
    """Cash Flow Statement report page."""
    if not start_date or not end_date:
        start_date, end_date = get_fiscal_year_dates()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Cash Flow Statement"
    context["start_date"] = start_date.isoformat()
    context["end_date"] = end_date.isoformat()
    context["report_type"] = "cash-flow"

    template = templates.get_template("reports/pages/cash_flow.html")
    return HTMLResponse(template.render(context))


@router.get("/general-ledger", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def general_ledger(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    account_id: Optional[int] = Query(None, description="Filter by account"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
):
    """General Ledger report page."""
    if not start_date or not end_date:
        start_date, end_date = get_default_dates()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "General Ledger"
    context["account_id"] = account_id
    context["start_date"] = start_date.isoformat()
    context["end_date"] = end_date.isoformat()
    context["report_type"] = "general-ledger"

    template = templates.get_template("reports/pages/general_ledger.html")
    return HTMLResponse(template.render(context))


@router.get("/receivables-aging", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def receivables_aging(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    as_of: Optional[date] = Query(None, description="As of date"),
):
    """Receivables Aging report page."""
    if not as_of:
        as_of = date.today()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Receivables Aging"
    context["as_of"] = as_of.isoformat()
    context["report_type"] = "receivables-aging"

    # Define aging buckets
    context["aging_buckets"] = ["Current", "1-30 Days", "31-60 Days", "61-90 Days", "90+ Days"]

    template = templates.get_template("reports/pages/receivables_aging.html")
    return HTMLResponse(template.render(context))


@router.get("/payables-aging", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def payables_aging(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    as_of: Optional[date] = Query(None, description="As of date"),
):
    """Payables Aging report page."""
    if not as_of:
        as_of = date.today()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Payables Aging"
    context["as_of"] = as_of.isoformat()
    context["report_type"] = "payables-aging"

    # Define aging buckets
    context["aging_buckets"] = ["Current", "1-30 Days", "31-60 Days", "61-90 Days", "90+ Days"]

    template = templates.get_template("reports/pages/payables_aging.html")
    return HTMLResponse(template.render(context))


@router.get("/financial-ratios", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def financial_ratios(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    as_of: Optional[date] = Query(None, description="As of date"),
):
    """Financial Ratios report page."""
    if not as_of:
        as_of = date.today()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Financial Ratios"
    context["as_of"] = as_of.isoformat()
    context["report_type"] = "financial-ratios"

    template = templates.get_template("reports/pages/financial_ratios.html")
    return HTMLResponse(template.render(context))


@router.get("/customer-balances", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def customer_balances(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    as_of: Optional[date] = Query(None, description="As of date"),
):
    """Customer Balances report page."""
    if not as_of:
        as_of = date.today()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Customer Balances"
    context["as_of"] = as_of.isoformat()
    context["report_type"] = "customer-balances"

    template = templates.get_template("reports/pages/customer_balances.html")
    return HTMLResponse(template.render(context))


@router.get("/supplier-balances", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def supplier_balances(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    as_of: Optional[date] = Query(None, description="As of date"),
):
    """Supplier Balances report page."""
    if not as_of:
        as_of = date.today()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Supplier Balances"
    context["as_of"] = as_of.isoformat()
    context["report_type"] = "supplier-balances"

    template = templates.get_template("reports/pages/supplier_balances.html")
    return HTMLResponse(template.render(context))


@router.get("/revenue-analysis", response_class=HTMLResponse, dependencies=[RequireReportsRead])
async def revenue_analysis(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
):
    """Revenue Analysis report page."""
    if not start_date or not end_date:
        start_date, end_date = get_fiscal_year_dates()

    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Revenue Analysis"
    context["start_date"] = start_date.isoformat()
    context["end_date"] = end_date.isoformat()
    context["report_type"] = "revenue-analysis"

    template = templates.get_template("reports/pages/revenue_analysis.html")
    return HTMLResponse(template.render(context))
