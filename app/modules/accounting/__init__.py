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
    id="finance",
    name="Finance",
    description="Accounting, purchasing, expenses, assets, and reporting",
    icon="book",
    prefix="/accounting",
    group="Finance",
    order=20,
    scopes=["accounting:read", "purchasing:read", "expenses:read", "assets:read", "reports:read"],
    prefixes=["/accounting", "/purchasing", "/expenses", "/assets", "/reports"],
)

NAVIGATION = [
    {
        "section": "Accounting",
        "href": "/accounting",
        "icon": "book",
        "scope": "accounting:read",
        "order": 10,
        "links": [
            {"label": "Accounts", "href": "/accounting/accounts", "icon": "list", "scope": "accounting:read"},
            {"label": "Journal Entries", "href": "/accounting/journal-entries", "icon": "book-open", "scope": "accounting:read"},
            {"label": "General Ledger", "href": "/accounting/general-ledger", "icon": "book", "scope": "accounting:read"},
            {"label": "AR Payments", "href": "/accounting/ar-payments", "icon": "credit-card", "scope": "accounting:read"},
            {"label": "AP Payments", "href": "/accounting/ap-payments", "icon": "credit-card", "scope": "accounting:read"},
            {"label": "Bank Accounts", "href": "/accounting/bank-accounts", "icon": "building", "scope": "accounting:read"},
            {"label": "Cost Centers", "href": "/accounting/cost-centers", "icon": "target", "scope": "accounting:read"},
            {"label": "Fiscal Periods", "href": "/accounting/fiscal-periods", "icon": "calendar", "scope": "accounting:read"},
        ],
    },
    {
        "section": "Sales",
        "href": "/accounting/invoices",
        "icon": "shopping-cart",
        "scope": "accounting:read",
        "order": 20,
        "links": [
            {"label": "Invoices", "href": "/accounting/invoices", "icon": "credit-card", "scope": "accounting:read"},
            {"label": "Credit Notes", "href": "/accounting/credit-notes", "icon": "file-minus", "scope": "accounting:read"},
        ],
    },
    {
        "section": "Purchases",
        "href": "/purchasing",
        "icon": "file-text",
        "scope": "purchasing:read",
        "order": 30,
        "links": [
            {"label": "Purchase Orders", "href": "/purchasing", "icon": "file-text", "scope": "purchasing:read"},
            {"label": "Suppliers", "href": "/suppliers", "icon": "truck", "scope": "suppliers:read"},
            {"label": "Bills", "href": "/suppliers/bills", "icon": "receipt", "scope": "suppliers:read"},
        ],
    },
    {
        "section": "Expenses",
        "href": "/expenses",
        "icon": "receipt",
        "scope": "expenses:read",
        "order": 40,
        "links": [
            {"label": "Expenses", "href": "/expenses", "icon": "receipt", "scope": "expenses:read"},
            {"label": "Categories", "href": "/expenses/categories", "icon": "list", "scope": "expenses:read"},
            {"label": "Advances", "href": "/expenses/advances", "icon": "dollar-sign", "scope": "expenses:read"},
        ],
    },
    {
        "section": "Assets",
        "href": "/assets",
        "icon": "box",
        "scope": "assets:read",
        "order": 50,
        "links": [
            {"label": "Assets", "href": "/assets", "icon": "box", "scope": "assets:read"},
            {"label": "Categories", "href": "/assets/categories", "icon": "folder", "scope": "assets:read"},
            {"label": "Depreciation", "href": "/assets/depreciation", "icon": "activity", "scope": "assets:read"},
        ],
    },
    {
        "section": "Reports",
        "href": "/reports",
        "icon": "bar-chart",
        "scope": "reports:read",
        "order": 60,
        "links": [
            {"label": "Balance Sheet", "href": "/reports/balance-sheet", "icon": "bar-chart", "scope": "reports:read"},
            {"label": "Income Statement", "href": "/reports/income-statement", "icon": "trending-up", "scope": "reports:read"},
            {"label": "Cash Flow", "href": "/reports/cash-flow", "icon": "dollar-sign", "scope": "reports:read"},
            {"label": "Trial Balance", "href": "/reports/trial-balance", "icon": "list", "scope": "reports:read"},
            {"label": "General Ledger", "href": "/reports/general-ledger", "icon": "book", "scope": "reports:read"},
            {"label": "Receivables Aging", "href": "/reports/receivables-aging", "icon": "clock", "scope": "reports:read"},
            {"label": "Payables Aging", "href": "/reports/payables-aging", "icon": "clock", "scope": "reports:read"},
            {"label": "Customer Balances", "href": "/reports/customer-balances", "icon": "users", "scope": "reports:read"},
            {"label": "Supplier Balances", "href": "/reports/supplier-balances", "icon": "truck", "scope": "reports:read"},
            {"label": "Revenue Analysis", "href": "/reports/revenue-analysis", "icon": "trending-up", "scope": "reports:read"},
            {"label": "Financial Ratios", "href": "/reports/financial-ratios", "icon": "activity", "scope": "reports:read"},
            {"label": "VAT Report", "href": "/reports/vat", "icon": "receipt", "scope": "reports:read"},
            {"label": "WHT Report", "href": "/reports/wht", "icon": "file-minus", "scope": "reports:read"},
            {"label": "PAYE Report", "href": "/reports/paye", "icon": "users", "scope": "reports:read"},
            {"label": "Tax Calendar", "href": "/reports/tax-calendar", "icon": "calendar", "scope": "reports:read"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]
