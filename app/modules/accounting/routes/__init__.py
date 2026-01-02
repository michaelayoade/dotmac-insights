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
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func

from app.web.dependencies import SessionUser, CSRFToken, DB
from app.web.context import get_base_context, get_navigation_context
from app.templates.environment import get_template_env

# Import models for dashboard stats
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.accounting import JournalEntry

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

    stats = []

    # Pending Invoices
    pending_invoices = db.query(func.count(Invoice.id)).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID])
    ).scalar() or 0
    stats.append({
        "key": "invoices",
        "label": "Pending Invoices",
        "value": f"{pending_invoices:,}",
        "subtext": "Awaiting payment",
        "icon": "file-text",
        "icon_bg": "bg-amber-50",
        "icon_color": "text-amber-600",
        "href": "/accounting/invoices",
    })

    # Total Receivables
    receivables = db.query(func.sum(Invoice.balance)).filter(
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE])
    ).scalar() or Decimal("0")
    stats.append({
        "key": "receivables",
        "label": "Receivables",
        "value": f"${receivables:,.0f}",
        "subtext": "Outstanding AR",
        "icon": "trending-up",
        "icon_bg": "bg-blue-50",
        "icon_color": "text-blue-600",
        "href": "/accounting/aging/ar",
    })

    # Today's Payments
    today = date.today()
    payments_today = db.query(func.count(Payment.id)).filter(
        func.date(Payment.payment_date) == today
    ).scalar() or 0
    stats.append({
        "key": "payments",
        "label": "Payments Today",
        "value": f"{payments_today:,}",
        "subtext": "Processed today",
        "icon": "credit-card",
        "icon_bg": "bg-emerald-50",
        "icon_color": "text-emerald-600",
        "href": "/accounting/payments",
    })

    # Journal Entries This Month
    month_start = date(today.year, today.month, 1)
    je_count = db.query(func.count(JournalEntry.id)).filter(
        JournalEntry.posting_date >= month_start
    ).scalar() or 0
    stats.append({
        "key": "journal",
        "label": "Journal Entries",
        "value": f"{je_count:,}",
        "subtext": "This month",
        "icon": "book-open",
        "icon_bg": "bg-purple-50",
        "icon_color": "text-purple-600",
        "href": "/accounting/journal-entries",
    })

    context["stats"] = stats

    context["quick_links"] = [
        {"label": "Accounts", "href": "/accounting/accounts", "icon": "list", "description": "Chart of accounts"},
        {"label": "Journal Entries", "href": "/accounting/journal-entries", "icon": "book-open", "description": "General ledger entries"},
        {"label": "Payments", "href": "/accounting/payments", "icon": "credit-card", "description": "AR & AP payments"},
        {"label": "Reports", "href": "/accounting/reports", "icon": "bar-chart", "description": "Financial reports"},
        {"label": "Bank Accounts", "href": "/accounting/bank-accounts", "icon": "building", "description": "Bank reconciliation"},
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

__all__ = ["router"]
