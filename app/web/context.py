"""
Template context builders for SSR pages.

Provides consistent context for all templates including:
- User information
- CSRF token
- Branding
- Flash messages
- Navigation data
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List, cast

from fastapi import Request, Response

from app.auth import Principal
from app.config import settings
from app.core.security import get_flash, FlashMessage
from app.currency import get_currency_symbol


def get_base_context(
    request: Request,
    response: Response,
    user: Optional[Principal] = None,
    csrf_token: str = "",
) -> Dict[str, Any]:
    """Build base context for all templates.

    Includes user info, branding, CSRF token, and flash messages.
    """
    # Get and clear flash message
    flash = get_flash(request, response)

    return {
        # Request info
        "request": request,
        "current_path": request.url.path,

        # User info
        "user": user,
        "is_authenticated": user is not None,

        # Permission helpers
        "has_scope": user.has_scope if user else lambda s: False,

        # Security
        "csrf_token": csrf_token,

        # Flash message
        "flash": flash,

        # Branding (from settings)
        "company_name": settings.company_name,
        "product_name": settings.product_name,
        "support_email": settings.support_email,
        "base_currency": settings.base_currency,
        "currency_symbol": get_currency_symbol(settings.base_currency),

        # Environment
        "is_production": settings.is_production,
        "environment": settings.environment,
    }


def build_breadcrumbs(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build breadcrumb navigation items.

    Args:
        items: List of {"label": "Name", "href": "/path"} dicts
               Last item should not have href (current page)

    Returns:
        List with is_current flag added to last item
    """
    if not items:
        return []

    result = []
    for i, item in enumerate(items):
        is_current = i == len(items) - 1
        result.append({
            "label": item["label"],
            "href": item.get("href") if not is_current else None,
            "is_current": is_current,
        })
    return result


def build_pagination_context(
    page: int,
    per_page: int,
    total: int,
) -> Dict[str, Any]:
    """Build pagination context for templates.

    Args:
        page: Current page (1-indexed)
        per_page: Items per page
        total: Total item count

    Returns:
        Dict with pagination info for templates
    """
    total_pages = max(1, (total + per_page - 1) // per_page)

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < total_pages else None,
        "start_item": ((page - 1) * per_page) + 1 if total > 0 else 0,
        "end_item": min(page * per_page, total),
    }


# Navigation structure for sidebar - Comprehensive navigation with all pages
# Note: Using "links" instead of "items" to avoid conflict with dict.items()
# Section can have optional "href" for clickable module landing pages
NAVIGATION_ITEMS: List[Dict[str, Any]] = [
    {
        "section": "Main",
        "links": [
            {"label": "Dashboard", "href": "/", "icon": "home", "scope": None},
            {"label": "Tasks", "href": "/tasks", "icon": "check-square", "scope": "tasks:read"},
        ],
    },
    {
        "section": "CRM",
        "href": "/crm",
        "scope": "crm:read",
        "links": [
            {"label": "Contacts", "href": "/crm/contacts", "icon": "users", "scope": "crm:read"},
            {"label": "Leads", "href": "/crm/leads", "icon": "user-plus", "scope": "crm:read"},
            {"label": "Customers", "href": "/customers", "icon": "building", "scope": "customers:read"},
            {"label": "Opportunities", "href": "/crm/opportunities", "icon": "trending-up", "scope": "crm:read"},
            {"label": "Pipeline", "href": "/crm/pipeline", "icon": "git-branch", "scope": "crm:read"},
            {"label": "Activities", "href": "/crm/activities", "icon": "activity", "scope": "crm:read"},
        ],
    },
    {
        "section": "Sales",
        "href": "/sales",
        "scope": "sales:read",
        "links": [
            {"label": "Quotations", "href": "/sales/quotations", "icon": "file-text", "scope": "sales:read"},
            {"label": "Orders", "href": "/sales/orders", "icon": "shopping-cart", "scope": "sales:read"},
            {"label": "Invoices", "href": "/invoices", "icon": "credit-card", "scope": "accounting:read"},
            {"label": "Credit Notes", "href": "/invoices/credit-notes", "icon": "file-minus", "scope": "accounting:read"},
            {"label": "Subscriptions", "href": "/subscriptions", "icon": "repeat", "scope": "subscriptions:read"},
            {"label": "Tariffs", "href": "/subscriptions/tariffs", "icon": "list", "scope": "subscriptions:read"},
        ],
    },
    {
        "section": "Finance",
        "href": "/accounting",
        "scope": "accounting:read",
        "links": [
            {"label": "Accounts", "href": "/accounting/accounts", "icon": "list", "scope": "accounting:read"},
            {"label": "Journal Entries", "href": "/accounting/journal-entries", "icon": "book-open", "scope": "accounting:read"},
            {"label": "General Ledger", "href": "/accounting/general-ledger", "icon": "book", "scope": "accounting:read"},
            {"label": "AR Payments", "href": "/accounting/ar-payments", "icon": "credit-card", "scope": "accounting:read"},
            {"label": "AP Payments", "href": "/accounting/ap-payments", "icon": "credit-card", "scope": "accounting:read"},
            {"label": "Bank Accounts", "href": "/accounting/bank-accounts", "icon": "building", "scope": "accounting:read"},
            {"label": "Cost Centers", "href": "/accounting/cost-centers", "icon": "target", "scope": "accounting:read"},
            {"label": "Fiscal Periods", "href": "/accounting/fiscal-periods", "icon": "calendar", "scope": "accounting:read"},
            {"label": "AP Aging", "href": "/accounting/aging/ap", "icon": "clock", "scope": "accounting:read"},
            {"label": "AR Aging", "href": "/accounting/aging/ar", "icon": "clock", "scope": "accounting:read"},
            {"label": "Approvals", "href": "/accounting/approvals", "icon": "check-circle", "scope": "accounting:read"},
            {"label": "Audit Log", "href": "/accounting/audit-log", "icon": "activity", "scope": "accounting:read"},
            {"label": "Workflows", "href": "/accounting/workflows", "icon": "git-branch", "scope": "accounting:read"},
            {"label": "Tax Codes", "href": "/accounting/tax-codes", "icon": "list", "scope": "accounting:read"},
            {"label": "Tax Filing", "href": "/accounting/tax/filing", "icon": "file-text", "scope": "accounting:read"},
        ],
    },
    {
        "section": "Reports",
        "href": "/reports",
        "scope": "reports:read",
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
    {
        "section": "Purchasing",
        "href": "/purchasing",
        "scope": "purchasing:read",
        "links": [
            {"label": "Purchase Orders", "href": "/purchasing", "icon": "file-text", "scope": "purchasing:read"},
            {"label": "Suppliers", "href": "/suppliers", "icon": "truck", "scope": "suppliers:read"},
            {"label": "Bills", "href": "/suppliers/bills", "icon": "receipt", "scope": "suppliers:read"},
            {"label": "Expenses", "href": "/expenses", "icon": "receipt", "scope": "expenses:read"},
            {"label": "Expense Categories", "href": "/expenses/categories", "icon": "list", "scope": "expenses:read"},
            {"label": "Advances", "href": "/expenses/advances", "icon": "dollar-sign", "scope": "expenses:read"},
        ],
    },
    {
        "section": "HR",
        "href": "/hr",
        "scope": "hr:read",
        "links": [
            {"label": "Employees", "href": "/hr/employees", "icon": "users", "scope": "hr:read"},
            {"label": "Departments", "href": "/hr/departments", "icon": "building", "scope": "hr:read"},
            {"label": "Designations", "href": "/hr/designations", "icon": "award", "scope": "hr:read"},
            {"label": "Leave Applications", "href": "/hr/leave", "icon": "calendar", "scope": "hr:read"},
            {"label": "Leave Types", "href": "/hr/leave/types", "icon": "list", "scope": "hr:read"},
            {"label": "Leave Allocations", "href": "/hr/leave/allocations", "icon": "check-square", "scope": "hr:read"},
            {"label": "Attendance", "href": "/hr/attendance", "icon": "clock", "scope": "hr:read"},
            {"label": "Shifts", "href": "/hr/attendance/shifts", "icon": "clock", "scope": "hr:read"},
            {"label": "Payroll Slips", "href": "/hr/payroll", "icon": "dollar-sign", "scope": "hr:read"},
            {"label": "Payroll Runs", "href": "/hr/payroll/runs", "icon": "repeat", "scope": "hr:read"},
            {"label": "Salary Structures", "href": "/hr/payroll/structures", "icon": "list", "scope": "hr:read"},
            {"label": "Training Events", "href": "/hr/training", "icon": "book", "scope": "hr:read"},
            {"label": "Training Programs", "href": "/hr/training/programs", "icon": "book-open", "scope": "hr:read"},
            {"label": "Appraisals", "href": "/hr/appraisal", "icon": "award", "scope": "hr:read"},
            {"label": "Appraisal Templates", "href": "/hr/appraisal/templates", "icon": "file-text", "scope": "hr:read"},
            {"label": "Job Openings", "href": "/hr/recruitment", "icon": "user-plus", "scope": "hr:read"},
            {"label": "Applicants", "href": "/hr/recruitment/applicants", "icon": "users", "scope": "hr:read"},
            {"label": "Interviews", "href": "/hr/recruitment/interviews", "icon": "calendar", "scope": "hr:read"},
            {"label": "Job Offers", "href": "/hr/recruitment/offers", "icon": "file-text", "scope": "hr:read"},
            {"label": "Onboarding", "href": "/hr/lifecycle/onboarding", "icon": "user-plus", "scope": "hr:read"},
            {"label": "Separations", "href": "/hr/lifecycle/separation", "icon": "user-minus", "scope": "hr:read"},
            {"label": "Promotions", "href": "/hr/lifecycle/promotions", "icon": "trending-up", "scope": "hr:read"},
            {"label": "Transfers", "href": "/hr/lifecycle/transfers", "icon": "repeat", "scope": "hr:read"},
            {"label": "Holidays", "href": "/hr/holidays", "icon": "calendar", "scope": "hr:read"},
            {"label": "Performance", "href": "/performance", "icon": "target", "scope": "performance:read"},
            {"label": "KPIs", "href": "/performance/kpis", "icon": "activity", "scope": "performance:read"},
            {"label": "KRAs", "href": "/performance/kras", "icon": "target", "scope": "performance:read"},
            {"label": "Scorecards", "href": "/performance/scorecards", "icon": "bar-chart", "scope": "performance:read"},
        ],
    },
    {
        "section": "Support",
        "href": "/support",
        "scope": "support:read",
        "links": [
            {"label": "Tickets", "href": "/support/tickets", "icon": "life-buoy", "scope": "support:read"},
            {"label": "Inbox", "href": "/inbox", "icon": "inbox", "scope": "support:read"},
            {"label": "Teams", "href": "/support/teams", "icon": "users", "scope": "support:read"},
            {"label": "Agents", "href": "/support/agents", "icon": "user", "scope": "support:read"},
            {"label": "Knowledge Base", "href": "/support/kb", "icon": "book-open", "scope": "support:read"},
            {"label": "KB Categories", "href": "/support/kb/categories", "icon": "folder", "scope": "support:read"},
            {"label": "Canned Responses", "href": "/support/canned-responses", "icon": "file-text", "scope": "support:read"},
            {"label": "SLA Policies", "href": "/support/sla", "icon": "clock", "scope": "support:read"},
            {"label": "SLA Calendars", "href": "/support/sla/calendars", "icon": "calendar", "scope": "support:read"},
            {"label": "SLA Breaches", "href": "/support/sla/breaches", "icon": "alert-circle", "scope": "support:read"},
            {"label": "Automation Logs", "href": "/support/automation/logs", "icon": "activity", "scope": "support:read"},
            {"label": "CSAT Analytics", "href": "/support/csat/analytics", "icon": "bar-chart", "scope": "support:read"},
            {"label": "Tags", "href": "/support/tags", "icon": "tag", "scope": "support:read"},
        ],
    },
    {
        "section": "Operations",
        "href": "/operations",
        "scope": "operations:read",
        "links": [
            {"label": "Projects", "href": "/projects", "icon": "folder", "scope": "projects:read"},
            {"label": "Project Tasks", "href": "/projects/tasks", "icon": "check-square", "scope": "projects:read"},
            {"label": "Milestones", "href": "/projects/milestones", "icon": "flag", "scope": "projects:read"},
            {"label": "Field Service", "href": "/field-service", "icon": "truck", "scope": "field_service:read"},
            {"label": "FS Teams", "href": "/field-service/teams", "icon": "users", "scope": "field_service:read"},
            {"label": "Technicians", "href": "/field-service/technicians", "icon": "user", "scope": "field_service:read"},
            {"label": "Warehouses", "href": "/inventory", "icon": "package", "scope": "inventory:read"},
            {"label": "Stock Entries", "href": "/inventory/stock-entries", "icon": "list", "scope": "inventory:read"},
            {"label": "Assets", "href": "/assets", "icon": "box", "scope": "assets:read"},
            {"label": "Asset Categories", "href": "/assets/categories", "icon": "folder", "scope": "assets:read"},
            {"label": "Vehicles", "href": "/vehicles", "icon": "truck", "scope": "vehicles:read"},
        ],
    },
    {
        "section": "Network",
        "href": "/network",
        "scope": "network:read",
        "links": [
            {"label": "POPs", "href": "/network/pops", "icon": "map-pin", "scope": "network:read"},
            {"label": "Routers", "href": "/network/routers", "icon": "server", "scope": "network:read"},
            {"label": "IP Management", "href": "/network/ip", "icon": "globe", "scope": "network:read"},
            {"label": "Networks", "href": "/network/ip/networks", "icon": "globe", "scope": "network:read"},
            {"label": "Addresses", "href": "/network/ip/addresses", "icon": "list", "scope": "network:read"},
        ],
    },
    {
        "section": "Analytics",
        "href": "/analytics",
        "scope": "analytics:read",
        "links": [
            {"label": "Insights", "href": "/analytics/insights", "icon": "activity", "scope": "analytics:read"},
            {"label": "Revenue", "href": "/analytics/revenue", "icon": "dollar-sign", "scope": "analytics:read"},
            {"label": "Customers", "href": "/analytics/customers", "icon": "users", "scope": "analytics:read"},
            {"label": "Operations", "href": "/analytics/operations", "icon": "truck", "scope": "analytics:read"},
            {"label": "HR Analytics", "href": "/analytics/hr", "icon": "users", "scope": "analytics:read"},
            {"label": "Support Analytics", "href": "/analytics/support", "icon": "life-buoy", "scope": "analytics:read"},
        ],
    },
    {
        "section": "Settings",
        "href": "/settings",
        "scope": "settings:read",
        "links": [
            {"label": "General", "href": "/settings", "icon": "settings", "scope": "settings:read"},
            {"label": "Accounting", "href": "/settings/books", "icon": "book", "scope": "books:settings:read"},
            {"label": "HR Settings", "href": "/settings/hr", "icon": "users", "scope": "hr:settings:read"},
            {"label": "Support Settings", "href": "/settings/support", "icon": "life-buoy", "scope": "support:settings:read"},
            {"label": "Asset Settings", "href": "/settings/assets", "icon": "box", "scope": "assets:settings:read"},
            {"label": "Data Sync", "href": "/settings/sync", "icon": "refresh-cw", "scope": "settings:sync"},
            {"label": "Data Migration", "href": "/settings/migration", "icon": "upload", "scope": "admin:write"},
            {"label": "Data Cleanup", "href": "/settings/data-cleanup", "icon": "check-circle", "scope": "admin:read"},
        ],
    },
    {
        "section": "Admin",
        "href": "/settings/admin",
        "scope": "admin:read",
        "links": [
            {"label": "Users", "href": "/settings/admin/users", "icon": "users", "scope": "admin:read"},
            {"label": "Roles", "href": "/settings/admin/roles", "icon": "shield", "scope": "admin:read"},
            {"label": "Groups", "href": "/settings/admin/groups", "icon": "users", "scope": "admin:read"},
            {"label": "Permissions", "href": "/settings/admin/permissions", "icon": "lock", "scope": "admin:read"},
            {"label": "Sessions", "href": "/settings/admin/sessions", "icon": "clock", "scope": "admin:read"},
            {"label": "API Tokens", "href": "/settings/admin/tokens", "icon": "key", "scope": "admin:read"},
            {"label": "Webhooks", "href": "/settings/admin/webhooks", "icon": "link", "scope": "admin:read"},
            {"label": "Audit Log", "href": "/settings/admin/audit", "icon": "activity", "scope": "admin:read"},
        ],
    },
]


def get_navigation_context(user: Optional[Principal]) -> List[Dict[str, Any]]:
    """Get filtered navigation based on user permissions.

    Removes sections where user has no access to any links.
    Includes section href for clickable module landing pages.
    """
    if not user:
        return []

    result = []
    for section in NAVIGATION_ITEMS:
        filtered_links = []
        for link in section["links"]:
            # No scope required or user has scope
            link_scope = cast(Optional[str], link.get("scope"))
            if link_scope is None or user.has_scope(link_scope):
                filtered_links.append(link)

        if filtered_links:
            section_data = {
                "section": section["section"],
                "links": filtered_links,
            }
            # Include section href if user has permission
            if section.get("href"):
                section_scope = cast(Optional[str], section.get("scope"))
                if section_scope is None or user.has_scope(section_scope):
                    section_data["href"] = section["href"]
            result.append(section_data)

    return result
