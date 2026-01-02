"""
Accounting Module - Financial Management and Reporting.

Routes:
- /accounting - Dashboard (landing page)
- /accounting/accounts - Chart of Accounts
- /accounting/journal-entries - Journal entry management
- /accounting/general-ledger - GL views
- /accounting/ar-payments - Accounts receivable payments
- /accounting/ap-payments - Accounts payable payments
- /accounting/bank-accounts - Banking
- /accounting/cost-centers - Cost center management
- /accounting/fiscal-periods - Fiscal period management
- /accounting/aging/* - AR/AP aging reports
- /accounting/approvals - Approval workflows
- /accounting/audit-log - Audit log views
- /accounting/workflows - Workflow configuration
- /accounting/tax-codes - Tax code management
- /accounting/tax/* - Tax filing and management
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="accounting",
    name="Accounting",
    description="Financial management, journal entries, and reporting",
    icon="book",
    prefix="/accounting",
    group="Back Office",
    order=20,
    scopes=["accounting:read"],
    prefixes=["/accounting"],
)

NAVIGATION = [
    {
        "section": "Finance",
        "module": "accounting",
        "href": "/accounting",
        "icon": "book",
        "scope": "accounting:read",
        "order": 20,
        "links": [
            {"label": "Dashboard", "href": "/accounting", "icon": "home"},
            {"label": "Accounts", "href": "/accounting/accounts", "icon": "list"},
            {"label": "Journal Entries", "href": "/accounting/journal-entries", "icon": "book-open"},
            {"label": "General Ledger", "href": "/accounting/general-ledger", "icon": "book"},
            {"label": "AR Payments", "href": "/accounting/ar-payments", "icon": "credit-card"},
            {"label": "AP Payments", "href": "/accounting/ap-payments", "icon": "credit-card"},
            {"label": "Bank Accounts", "href": "/accounting/bank-accounts", "icon": "building"},
            {"label": "Cost Centers", "href": "/accounting/cost-centers", "icon": "target"},
            {"label": "Fiscal Periods", "href": "/accounting/fiscal-periods", "icon": "calendar"},
            {"label": "AP Aging", "href": "/accounting/aging/ap", "icon": "clock"},
            {"label": "AR Aging", "href": "/accounting/aging/ar", "icon": "clock"},
            {"label": "Approvals", "href": "/accounting/approvals", "icon": "check-circle"},
            {"label": "Audit Log", "href": "/accounting/audit-log", "icon": "activity"},
            {"label": "Workflows", "href": "/accounting/workflows", "icon": "git-branch"},
            {"label": "Tax Codes", "href": "/accounting/tax-codes", "icon": "list"},
            {"label": "Tax Filing", "href": "/accounting/tax/filing", "icon": "file-text"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]
