"""
Accounting Routes - Modular Router Aggregator

This module aggregates all accounting route modules into a single router.
Each module handles a specific domain:
- Dashboard (landing page)
- invoices: Invoice CRUD
- payments: Payment CRUD (including AR/AP payments)
- accounts: Chart of Accounts
- journal_entries: Journal Entry management
- general_ledger: GL views
- reports: Financial reports
- bank_accounts: Banking
- fiscal_periods: Fiscal period management
- aging: AR/AP aging reports
- suppliers: Supplier management
- cost_centers: Cost center management
- audit_log: Audit log views
- approvals: Approval workflow management
- tax: Tax codes and rates
- payment_terms: Payment terms templates
- notes: Document notes
- payment_modes: Payment modes (Cash, Bank, etc.)
- attachments: Document attachment management
"""
from __future__ import annotations

from datetime import datetime, date

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse

from app.web.dependencies import SessionUser, CSRFToken, DB
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env

from app.services.accounting import (
    AccountingSettingsService,
    BankingService,
    DashboardService,
    PayablesService,
    ReceivablesService,
    ReportsService,
)
from app.services.accounting.dashboard_types import DashboardFilters
from app.services.accounting.reports_types import BalanceSheetParams, CashFlowParams, IncomeStatementParams

# Import all route modules
from .invoices import router as invoices_router
from .payments import router as payments_router
from .accounts import router as accounts_router
from .journal_entries import router as journal_entries_router
from .general_ledger import router as general_ledger_router
from .reports import router as reports_router
from .bank_accounts import router as bank_accounts_router
from .fiscal_periods import router as fiscal_periods_router
from .aging import router as aging_router
from .suppliers import router as suppliers_router
from .cost_centers import router as cost_centers_router
from .audit_log import router as audit_log_router
from .approvals import router as approvals_router
from .tax import router as tax_router
from .payment_terms import router as payment_terms_router
from .notes import router as notes_router
from .payment_modes import router as payment_modes_router
from .attachments import router as attachments_router

templates = get_template_env()

# Create the main accounting router
router = APIRouter(prefix="/accounting", tags=["accounting"])


@router.get("", response_class=HTMLResponse)
async def accounting_dashboard(
    request: Request,
    response: Response,
    user: SessionUser,
    csrf_token: CSRFToken,
    db: DB,
):
    """Accounting dashboard - landing page."""
    context = get_base_context(request, response, user, csrf_token)
    context["navigation"] = get_navigation_context(user)
    context["page_title"] = "Accounting"
    context["now"] = datetime.utcnow()

    settings_service = AccountingSettingsService(db, user)
    dashboard_service = DashboardService(db, settings_service, user)
    reports_service = ReportsService(db, user)
    receivables_service = ReceivablesService(db, settings_service, user)
    payables_service = PayablesService(db, settings_service, user)
    banking_service = BankingService(db, user)

    end_date = date.today()
    start_date = date(end_date.year, 1, 1)

    dashboard = dashboard_service.get_dashboard(
        DashboardFilters(start_date=start_date, end_date=end_date)
    )
    balance_sheet = reports_service.get_balance_sheet(
        BalanceSheetParams(as_of_date=end_date)
    )
    income_statement = reports_service.get_income_statement(
        IncomeStatementParams(start_date=start_date, end_date=end_date)
    )
    cash_flow = reports_service.get_cash_flow(
        CashFlowParams(start_date=start_date, end_date=end_date, limit=5)
    )

    receivables_summary = receivables_service.get_outstanding_summary(top_n=5)
    payables_summary = payables_service.get_outstanding_summary(top_n=5)
    bank_accounts = banking_service.list_bank_accounts(
        include_disabled=False,
        as_of_date=end_date,
    )

    summary_cards = [
        {
            "label": "Total Assets",
            "value": f"{dashboard.summary.total_assets:,.2f}",
            "subtext": "Balance sheet",
            "icon": "trending-up",
            "icon_bg": "bg-emerald-50",
            "icon_color": "text-emerald-600",
        },
        {
            "label": "Total Liabilities",
            "value": f"{dashboard.summary.total_liabilities:,.2f}",
            "subtext": "Balance sheet",
            "icon": "inbox",
            "icon_bg": "bg-red-50",
            "icon_color": "text-red-600",
        },
        {
            "label": "Net Worth",
            "value": f"{dashboard.summary.net_worth:,.2f}",
            "subtext": "Assets minus liabilities",
            "icon": "award",
            "icon_bg": "bg-blue-50",
            "icon_color": "text-blue-600",
        },
        {
            "label": "Net Profit",
            "value": f"{dashboard.performance.net_profit:,.2f}",
            "subtext": "Year to date",
            "icon": "bar-chart",
            "icon_bg": "bg-amber-50",
            "icon_color": "text-amber-600",
        },
        {
            "label": "Receivables",
            "value": f"{receivables_summary.total_outstanding:,.2f}",
            "subtext": "Outstanding AR",
            "icon": "file-text",
            "icon_bg": "bg-indigo-50",
            "icon_color": "text-indigo-600",
        },
        {
            "label": "Payables",
            "value": f"{payables_summary.total_outstanding:,.2f}",
            "subtext": "Outstanding AP",
            "icon": "receipt",
            "icon_bg": "bg-orange-50",
            "icon_color": "text-orange-600",
        },
    ]

    context["summary_cards"] = summary_cards
    context["dashboard"] = dashboard
    context["balance_sheet"] = balance_sheet
    context["income_statement"] = income_statement
    context["cash_flow"] = cash_flow
    context["receivables_summary"] = receivables_summary
    context["payables_summary"] = payables_summary
    context["bank_accounts"] = bank_accounts["accounts"]
    context["bank_total_balance"] = bank_accounts["total_balance"]

    context["quick_links"] = [
        {"label": "Accounts", "href": "/accounting/accounts", "icon": "list", "description": "Chart of accounts"},
        {"label": "Journal Entries", "href": "/accounting/journal-entries", "icon": "book-open", "description": "General ledger entries"},
        {"label": "Payments", "href": "/accounting/payments", "icon": "credit-card", "description": "AR & AP payments"},
        {"label": "Reports", "href": "/accounting/reports/trial-balance", "icon": "bar-chart", "description": "Financial reports"},
        {"label": "Bank Accounts", "href": "/accounting/bank-accounts", "icon": "building", "description": "Bank reconciliation"},
        {"label": "Tax Filing", "href": "/accounting/tax/filing", "icon": "file-text", "description": "Tax obligations"},
        {"label": "Approvals", "href": "/accounting/approvals", "icon": "check-circle", "description": "Approval workflows"},
        {"label": "Financial Ratios", "href": "/accounting/reports/financial-ratios", "icon": "target", "description": "Liquidity and profitability"},
    ]

    template = templates.get_template("modules/accounting/templates/pages/dashboard.html")
    return HTMLResponse(template.render(context))


# Include all sub-routers
router.include_router(invoices_router)
router.include_router(payments_router)
router.include_router(accounts_router)
router.include_router(journal_entries_router)
router.include_router(general_ledger_router)
router.include_router(reports_router)
router.include_router(bank_accounts_router)
router.include_router(fiscal_periods_router)
router.include_router(aging_router)
router.include_router(suppliers_router)
router.include_router(cost_centers_router)
router.include_router(audit_log_router)
router.include_router(approvals_router)
router.include_router(tax_router)
router.include_router(payment_terms_router)
router.include_router(notes_router)
router.include_router(payment_modes_router)
router.include_router(attachments_router)

__all__ = ["router"]
