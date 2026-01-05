"""
Reports Module - Financial and Business Reports.

Routes:
- /reports - Reports dashboard
- /reports/balance-sheet - Balance sheet report
- /reports/income-statement - Income statement
- /reports/cash-flow - Cash flow statement
- /reports/trial-balance - Trial balance
- /reports/general-ledger - General ledger report
- /reports/receivables-aging - AR aging
- /reports/payables-aging - AP aging
- /reports/customer-balances - Customer balance report
- /reports/supplier-balances - Supplier balance report
- /reports/revenue-analysis - Revenue analysis
- /reports/financial-ratios - Financial ratios
- /reports/vat - VAT report
- /reports/wht - WHT report
- /reports/paye - PAYE report
- /reports/tax-calendar - Tax calendar
"""
from __future__ import annotations

from app.web.module_types import ModuleConfig

# =============================================================================
# Module Configuration (for auto-discovery)
# =============================================================================

MODULE_CONFIG = ModuleConfig(
    id="reports",
    name="Reports",
    description="Financial reports, tax reports, and analytics",
    icon="bar-chart",
    prefix="/reports",
    group="Back Office",
    order=28,
    scopes=["reports:read"],
    enabled=False,
    prefixes=["/reports"],
)

NAVIGATION = [
    {
        "section": "Reports",
        "module": "reports",
        "href": "/reports",
        "icon": "bar-chart",
        "scope": "reports:read",
        "order": 28,
        "links": [
            {"label": "Balance Sheet", "href": "/reports/balance-sheet", "icon": "bar-chart"},
            {"label": "Income Statement", "href": "/reports/income-statement", "icon": "trending-up"},
            {"label": "Cash Flow", "href": "/reports/cash-flow", "icon": "dollar-sign"},
            {"label": "Trial Balance", "href": "/reports/trial-balance", "icon": "list"},
            {"label": "General Ledger", "href": "/reports/general-ledger", "icon": "book"},
            {"label": "Receivables Aging", "href": "/reports/receivables-aging", "icon": "clock"},
            {"label": "Payables Aging", "href": "/reports/payables-aging", "icon": "clock"},
            {"label": "Customer Balances", "href": "/reports/customer-balances", "icon": "users"},
            {"label": "Supplier Balances", "href": "/reports/supplier-balances", "icon": "truck"},
            {"label": "Revenue Analysis", "href": "/reports/revenue-analysis", "icon": "trending-up"},
            {"label": "Financial Ratios", "href": "/reports/financial-ratios", "icon": "activity"},
            {"label": "VAT Report", "href": "/reports/vat", "icon": "receipt"},
            {"label": "WHT Report", "href": "/reports/wht", "icon": "file-minus"},
            {"label": "PAYE Report", "href": "/reports/paye", "icon": "users"},
            {"label": "Tax Calendar", "href": "/reports/tax-calendar", "icon": "calendar"},
        ],
    },
]

# =============================================================================
# Router Export (for auto-discovery)
# =============================================================================

from .routes import router

__all__ = ["MODULE_CONFIG", "NAVIGATION", "router"]
