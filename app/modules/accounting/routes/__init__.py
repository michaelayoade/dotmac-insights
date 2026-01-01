"""
Accounting Routes - Modular Router Aggregator

This module aggregates all accounting route modules into a single router.
Each module handles a specific domain:
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
from fastapi import APIRouter

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

# Create the main accounting router
router = APIRouter(prefix="/accounting", tags=["accounting"])

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

__all__ = ["router"]
