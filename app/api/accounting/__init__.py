"""
Accounting Module Router

Combines all accounting sub-modules into a single router.
This module replaces the monolithic app/api/accounting.py with a
structured decomposition into focused sub-routers.

Sub-modules:
- dashboard: Overview metrics and KPIs
- reports: Financial statements (TB, BS, P&L, Cash Flow, etc.)
- ledger: GL entries, Chart of Accounts, account details
- journal_entries: Journal entry CRUD and posting workflows
- receivables: AR, aging, dunning, credit management
- payables: AP, suppliers, aging
- banking: Bank accounts, transactions, reconciliation, CRUD
- fiscal: Fiscal years, periods, cost centers
- workflows: Approval workflows, controls, audit log
- tax: Tax templates, filing, payments
- exports: Report exports (CSV/PDF)
- tax_codes: Tax code entities with rates and jurisdiction
- payment_terms: Payment terms templates and due date calculation
- ap_payments: Supplier payments with allocations and workflow
- ar_payments: Customer payments with allocations
- notes: Credit notes (AR) and debit notes (AP)
- attachments: Document attachment upload and management
"""

from fastapi import APIRouter

from .dashboard import router as dashboard_router
from .reports import router as reports_router
from .ledger import router as ledger_router
from .receivables import router as receivables_router
from .payables import router as payables_router
from .banking import router as banking_router
from .journal_entries import router as journal_entries_router
from .fiscal import router as fiscal_router
from .workflows import router as workflows_router
from .tax import router as tax_router
from .exports import router as exports_router
from .tax_codes import router as tax_codes_router
from .payment_terms import router as payment_terms_router
from .ap_payments import router as ap_payments_router
from .ar_payments import router as ar_payments_router
from .notes import router as notes_router
from .attachments import router as attachments_router

router = APIRouter(tags=["accounting"])

# Include sub-routers
router.include_router(dashboard_router)
router.include_router(reports_router, tags=["Accounting - Reports"])
router.include_router(ledger_router, tags=["Accounting - Ledger"])
router.include_router(receivables_router, tags=["Accounting - Receivables"])
router.include_router(payables_router, tags=["Accounting - Payables"])
router.include_router(banking_router, tags=["Accounting - Banking"])
router.include_router(journal_entries_router, tags=["Accounting - Journal Entries"])
router.include_router(fiscal_router, tags=["Accounting - Fiscal"])
router.include_router(workflows_router, tags=["Accounting - Workflows"])
router.include_router(tax_router, tags=["Accounting - Tax"])
router.include_router(exports_router, tags=["Accounting - Exports"])
router.include_router(tax_codes_router, tags=["Accounting - Tax Codes"])
router.include_router(payment_terms_router, tags=["Accounting - Payment Terms"])
router.include_router(ap_payments_router, tags=["Accounting - AP Payments"])
router.include_router(ar_payments_router, tags=["Accounting - AR Payments"])
router.include_router(notes_router, tags=["Accounting - Credit/Debit Notes"])
router.include_router(attachments_router, tags=["Accounting - Attachments"])

# Re-export common items for convenience
from .helpers import (
    parse_date,
    get_fiscal_year_dates,
    resolve_currency_or_raise,
    paginate,
    invalidate_report_cache,
    serialize_account,
    serialize_gl_entry,
)

__all__ = [
    "router",
    "parse_date",
    "get_fiscal_year_dates",
    "resolve_currency_or_raise",
    "paginate",
    "invalidate_report_cache",
    "serialize_account",
    "serialize_gl_entry",
]
