"""
Module Page Smoke Tests.

Iterates through all GET routes in each module and verifies pages load without server errors.
This ensures all SSR pages are accessible and templates render correctly.

Run with: pytest tests/e2e/test_module_pages.py -v
Run single module: pytest tests/e2e/test_module_pages.py -v -k "crm"
"""

import re
import pytest
import httpx
from typing import Optional
from dataclasses import dataclass


# Base URL for the application
BASE_URL = "http://localhost:8000"

# Test timeout
TIMEOUT = 10


@dataclass
class PageRoute:
    """Represents a page route to test."""
    path: str
    name: str
    module: str
    requires_id: bool = False


def substitute_path_params(path: str) -> str:
    """Replace path parameters with test values."""
    substitutions = {
        "{account_id}": "1",
        "{contact_id}": "1",
        "{lead_id}": "1",
        "{opportunity_id}": "1",
        "{activity_id}": "1",
        "{campaign_id}": "1",
        "{ticket_id}": "1",
        "{invoice_id}": "1",
        "{payment_id}": "1",
        "{customer_id}": "1",
        "{supplier_id}": "1",
        "{expense_id}": "1",
        "{project_id}": "1",
        "{task_id}": "1",
        "{milestone_id}": "1",
        "{employee_id}": "1",
        "{department_id}": "1",
        "{leave_id}": "1",
        "{subscription_id}": "1",
        "{tariff_id}": "1",
        "{order_id}": "1",
        "{quotation_id}": "1",
        "{product_id}": "1",
        "{bundle_id}": "1",
        "{item_id}": "1",
        "{team_id}": "1",
        "{agent_id}": "1",
        "{article_id}": "1",
        "{category_id}": "1",
        "{tag_id}": "1",
        "{sla_id}": "1",
        "{rule_id}": "1",
        "{automation_id}": "1",
        "{channel_id}": "1",
        "{conversation_id}": "1",
        "{router_id}": "1",
        "{pop_id}": "1",
        "{network_id}": "1",
        "{address_id}": "1",
        "{vehicle_id}": "1",
        "{job_id}": "1",
        "{scan_id}": "1",
        "{issue_id}": "1",
        "{filing_id}": "1",
        "{code_id}": "1",
        "{period_id}": "1",
        "{entry_id}": "1",
        "{workflow_id}": "1",
        "{approval_id}": "1",
        "{tab_name}": "overview",
        "{list_id}": "1",
        "{year}": "2024",
        "{month}": "01",
    }

    result = path
    for param, value in substitutions.items():
        result = result.replace(param, value)

    # Handle any remaining {param} patterns
    result = re.sub(r"\{[^}]+\}", "1", result)

    return result


def has_path_params(path: str) -> bool:
    """Check if path contains parameters."""
    return "{" in path


# Define module routes to test
# These are the main page routes (not API, not partials)
MODULE_ROUTES = {
    "crm": [
        PageRoute("/crm", "dashboard", "crm"),
        PageRoute("/crm/leads", "leads_list", "crm"),
        PageRoute("/crm/leads/new", "leads_new", "crm"),
        PageRoute("/crm/leads/{lead_id}", "lead_detail", "crm", requires_id=True),
        PageRoute("/crm/accounts", "accounts_list", "crm"),
        PageRoute("/crm/accounts/new", "accounts_new", "crm"),
        PageRoute("/crm/accounts/{account_id}", "account_detail", "crm", requires_id=True),
        PageRoute("/crm/contacts", "contacts_list", "crm"),
        PageRoute("/crm/contacts/new", "contacts_new", "crm"),
        PageRoute("/crm/contacts/{contact_id}", "contact_detail", "crm", requires_id=True),
        PageRoute("/crm/opportunities", "opportunities_list", "crm"),
        PageRoute("/crm/opportunities/new", "opportunities_new", "crm"),
        PageRoute("/crm/activities", "activities_list", "crm"),
        PageRoute("/crm/campaigns", "campaigns_list", "crm"),
    ],
    "sales": [
        PageRoute("/sales", "dashboard", "sales"),
        PageRoute("/sales/quotations", "quotations_list", "sales"),
        PageRoute("/sales/quotations/new", "quotations_new", "sales"),
        PageRoute("/sales/quotations/{quotation_id}", "quotation_detail", "sales", requires_id=True),
        PageRoute("/sales/orders", "orders_list", "sales"),
        PageRoute("/sales/orders/{order_id}", "order_detail", "sales", requires_id=True),
    ],
    "support": [
        PageRoute("/support", "dashboard", "support"),
        PageRoute("/support/tickets", "tickets_list", "support"),
        PageRoute("/support/tickets/new", "tickets_new", "support"),
        PageRoute("/support/tickets/{ticket_id}", "ticket_detail", "support", requires_id=True),
        PageRoute("/support/teams", "teams_list", "support"),
        PageRoute("/support/agents", "agents_list", "support"),
        PageRoute("/support/kb", "kb_list", "support"),
        PageRoute("/support/sla", "sla_list", "support"),
        PageRoute("/support/tags", "tags_list", "support"),
        PageRoute("/support/csat/analytics", "csat_analytics", "support"),
    ],
    "accounting": [
        PageRoute("/accounting", "dashboard", "accounting"),
        PageRoute("/accounting/invoices", "invoices_list", "accounting"),
        PageRoute("/accounting/invoices/{invoice_id}", "invoice_detail", "accounting", requires_id=True),
        PageRoute("/accounting/payments/ar", "ar_payments_list", "accounting"),
        PageRoute("/accounting/payments/ap", "ap_payments_list", "accounting"),
        PageRoute("/accounting/credit-notes", "credit_notes_list", "accounting"),
        PageRoute("/accounting/debit-notes", "debit_notes_list", "accounting"),
        PageRoute("/accounting/journal-entries", "journal_entries_list", "accounting"),
        PageRoute("/accounting/accounts", "accounts_list", "accounting"),
        PageRoute("/accounting/suppliers", "suppliers_list", "accounting"),
        PageRoute("/accounting/bank-accounts", "bank_accounts_list", "accounting"),
        PageRoute("/accounting/cost-centers", "cost_centers_list", "accounting"),
        PageRoute("/accounting/fiscal-periods", "fiscal_periods_list", "accounting"),
        PageRoute("/accounting/payment-terms", "payment_terms_list", "accounting"),
        PageRoute("/accounting/payment-modes", "payment_modes_list", "accounting"),
        PageRoute("/accounting/tax/codes", "tax_codes_list", "accounting"),
        PageRoute("/accounting/tax/filings", "tax_filings_list", "accounting"),
        PageRoute("/accounting/approvals", "approvals_list", "accounting"),
        PageRoute("/accounting/general-ledger", "general_ledger", "accounting"),
        PageRoute("/accounting/reports/trial-balance", "trial_balance", "accounting"),
        PageRoute("/accounting/reports/balance-sheet", "balance_sheet", "accounting"),
        PageRoute("/accounting/reports/income-statement", "income_statement", "accounting"),
        PageRoute("/accounting/reports/cash-flow", "cash_flow", "accounting"),
        PageRoute("/accounting/aging/ar", "ar_aging", "accounting"),
        PageRoute("/accounting/aging/ap", "ap_aging", "accounting"),
    ],
    "purchasing": [
        PageRoute("/purchasing", "dashboard", "purchasing"),
        PageRoute("/purchasing/expenses", "expenses_list", "purchasing"),
        PageRoute("/purchasing/bills", "bills_list", "purchasing"),
        PageRoute("/purchasing/payments", "payments_list", "purchasing"),
        PageRoute("/purchasing/debit-notes", "debit_notes", "purchasing"),
        PageRoute("/purchasing/analytics", "analytics", "purchasing"),
        PageRoute("/purchasing/aging", "aging", "purchasing"),
    ],
    "expenses": [
        PageRoute("/expenses", "expenses_list", "expenses"),
        PageRoute("/expenses/new", "expenses_new", "expenses"),
        PageRoute("/expenses/{expense_id}", "expense_detail", "expenses", requires_id=True),
        PageRoute("/expenses/advances", "advances_list", "expenses"),
        PageRoute("/expenses/categories", "categories_list", "expenses"),
    ],
    "projects": [
        PageRoute("/projects", "dashboard", "projects"),
        PageRoute("/projects/list", "projects_list", "projects"),
        PageRoute("/projects/new", "projects_new", "projects"),
        PageRoute("/projects/{project_id}", "project_detail", "projects", requires_id=True),
        PageRoute("/projects/gantt", "gantt", "projects"),
    ],
    "hr": [
        PageRoute("/hr", "dashboard", "hr"),
        PageRoute("/hr/employees", "employees_list", "hr"),
        PageRoute("/hr/employees/new", "employees_new", "hr"),
        PageRoute("/hr/employees/{employee_id}", "employee_detail", "hr", requires_id=True),
        PageRoute("/hr/departments", "departments_list", "hr"),
        PageRoute("/hr/designations", "designations_list", "hr"),
        PageRoute("/hr/leave", "leave_list", "hr"),
        PageRoute("/hr/attendance", "attendance_list", "hr"),
        PageRoute("/hr/payroll", "payroll_list", "hr"),
        PageRoute("/hr/recruitment", "recruitment_list", "hr"),
        PageRoute("/hr/training", "training_list", "hr"),
        PageRoute("/hr/appraisal", "appraisal_list", "hr"),
        PageRoute("/hr/teams", "teams_list", "hr"),
        PageRoute("/hr/holidays", "holidays_list", "hr"),
        PageRoute("/hr/org-chart", "org_chart", "hr"),
        PageRoute("/hr/my/leave", "my_leave", "hr"),
        PageRoute("/hr/my/attendance", "my_attendance", "hr"),
        PageRoute("/hr/my/payslips", "my_payslips", "hr"),
    ],
    "subscriptions": [
        PageRoute("/subscriptions", "dashboard", "subscriptions"),
        PageRoute("/subscriptions/list", "subscriptions_list", "subscriptions"),
        PageRoute("/subscriptions/new", "subscriptions_new", "subscriptions"),
        PageRoute("/subscriptions/{subscription_id}", "subscription_detail", "subscriptions", requires_id=True),
        PageRoute("/subscriptions/tariffs", "tariffs_list", "subscriptions"),
        PageRoute("/subscriptions/payment-subscriptions", "payment_subscriptions_list", "subscriptions"),
        PageRoute("/subscriptions/bundles", "bundles_dashboard", "subscriptions"),
        PageRoute("/subscriptions/bundles/products", "bundles_products_list", "subscriptions"),
    ],
    "network": [
        PageRoute("/network", "dashboard", "network"),
        PageRoute("/network/routers", "routers_list", "network"),
        PageRoute("/network/routers/{router_id}", "router_detail", "network", requires_id=True),
        PageRoute("/network/pops", "pops_list", "network"),
        PageRoute("/network/pops/{pop_id}", "pop_detail", "network", requires_id=True),
        PageRoute("/network/networks", "networks_list", "network"),
        PageRoute("/network/addresses", "addresses_list", "network"),
        PageRoute("/network/ip-management", "ip_management", "network"),
        PageRoute("/network/health", "health", "network"),
        PageRoute("/network/analytics", "analytics", "network"),
    ],
    "field_service": [
        PageRoute("/field-service", "dashboard", "field_service"),
        PageRoute("/field-service/orders", "orders_list", "field_service"),
        PageRoute("/field-service/orders/new", "orders_new", "field_service"),
        PageRoute("/field-service/orders/{order_id}", "order_detail", "field_service", requires_id=True),
        PageRoute("/field-service/calendar", "calendar", "field_service"),
        PageRoute("/field-service/dispatch", "dispatch", "field_service"),
        PageRoute("/field-service/teams", "teams_list", "field_service"),
        PageRoute("/field-service/technicians", "technicians_list", "field_service"),
    ],
    "inventory": [
        PageRoute("/inventory", "dashboard", "inventory"),
        PageRoute("/inventory/items", "items_list", "inventory"),
        PageRoute("/inventory/items/new", "items_new", "inventory"),
        PageRoute("/inventory/warehouses", "warehouses_list", "inventory"),
        PageRoute("/inventory/stock-entries", "stock_entries_list", "inventory"),
    ],
    "vehicles": [
        PageRoute("/vehicles", "vehicles_list", "vehicles"),
    ],
    "reports": [
        PageRoute("/reports", "dashboard", "reports"),
        PageRoute("/reports/vat", "vat_report", "reports"),
        PageRoute("/reports/paye", "paye_report", "reports"),
        PageRoute("/reports/wht", "wht_report", "reports"),
        PageRoute("/reports/tax-calendar", "tax_calendar", "reports"),
    ],
    "settings": [
        PageRoute("/settings", "settings_home", "settings"),
        PageRoute("/settings/admin/users", "users_list", "settings"),
        PageRoute("/settings/admin/groups", "groups_list", "settings"),
        PageRoute("/settings/admin/sessions", "sessions_list", "settings"),
        PageRoute("/settings/sync", "sync_dashboard", "settings"),
        PageRoute("/settings/cleanup", "cleanup_dashboard", "settings"),
    ],
}


@pytest.fixture(scope="module")
def auth_cookies() -> dict:
    """Get authentication cookies for protected endpoints."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
            # Try form-based login
            response = client.post(
                "/auth/login",
                data={"email": "admin@dotmac.ng", "password": "admin123"},
                follow_redirects=False,
            )
            if response.status_code in (302, 303, 307):
                return dict(response.cookies)

            # Try JSON login
            response = client.post(
                "/api/auth/token",
                json={"email": "admin@dotmac.ng", "password": "admin123"},
            )
            if response.status_code == 200:
                token = response.json().get("access_token", "")
                return {"session": token}

    except Exception as e:
        print(f"Auth failed: {e}")

    return {}


class TestModulePages:
    """Test all pages in each module load without errors."""

    @pytest.mark.parametrize("module_name", list(MODULE_ROUTES.keys()))
    def test_module_pages_load(self, module_name: str, auth_cookies: dict):
        """Test all pages in a module load without server errors."""
        routes = MODULE_ROUTES[module_name]
        results = {"passed": 0, "failed": 0, "not_found": 0, "auth_required": 0}
        failures = []

        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, cookies=auth_cookies) as client:
            for route in routes:
                url = substitute_path_params(route.path)

                try:
                    response = client.get(url, follow_redirects=True)

                    if response.status_code == 200:
                        # Check for server error content in page
                        content = response.text.lower()
                        if "internal server error" in content or "traceback" in content:
                            failures.append(f"{route.path}: 200 but contains error")
                            results["failed"] += 1
                        else:
                            results["passed"] += 1
                    elif response.status_code == 404:
                        if route.requires_id:
                            # 404 for ID routes is expected if no test data
                            results["not_found"] += 1
                        else:
                            failures.append(f"{route.path}: 404")
                            results["failed"] += 1
                    elif response.status_code in (401, 403):
                        results["auth_required"] += 1
                    elif response.status_code >= 500:
                        failures.append(f"{route.path}: {response.status_code}")
                        results["failed"] += 1
                    else:
                        # 3xx, other 4xx - count as passed if not error
                        results["passed"] += 1

                except httpx.TimeoutException:
                    failures.append(f"{route.path}: timeout")
                    results["failed"] += 1
                except Exception as e:
                    failures.append(f"{route.path}: {str(e)[:50]}")
                    results["failed"] += 1

        # Report results
        total = len(routes)
        print(f"\n{module_name.upper()}: {results['passed']}/{total} passed, "
              f"{results['failed']} failed, {results['not_found']} not_found (ID routes)")

        if failures:
            print("  Failures:")
            for f in failures:
                print(f"    - {f}")

        # Assert no server errors (allow 404 for ID routes, auth issues)
        assert results["failed"] == 0, f"Module {module_name} has page failures: {failures}"


class TestCriticalPages:
    """Test critical pages that must always work."""

    CRITICAL_PAGES = [
        "/",
        "/crm",
        "/accounting",
        "/hr",
        "/support",
        "/subscriptions",
        "/projects",
    ]

    @pytest.mark.critical
    @pytest.mark.parametrize("path", CRITICAL_PAGES)
    def test_critical_page_loads(self, path: str, auth_cookies: dict):
        """Verify critical landing pages respond without server errors."""
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, cookies=auth_cookies) as client:
            response = client.get(path, follow_redirects=True)

            # Should not return server errors
            assert response.status_code < 500, f"{path} returned {response.status_code}"

            # Should have some content
            assert len(response.text) > 100, f"{path} returned empty or tiny response"


class TestPageContentIntegrity:
    """Test that pages render with expected content."""

    @pytest.mark.parametrize("path,expected_text", [
        ("/crm", "CRM"),
        ("/crm/accounts", "Accounts"),
        ("/crm/contacts", "Contacts"),
        ("/accounting/invoices", "Invoices"),
        ("/support/tickets", "Tickets"),
        ("/hr/employees", "Employees"),
    ])
    def test_page_has_expected_content(self, path: str, expected_text: str, auth_cookies: dict):
        """Verify pages contain expected text."""
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, cookies=auth_cookies) as client:
            response = client.get(path, follow_redirects=True)

            if response.status_code == 200:
                assert expected_text.lower() in response.text.lower(), \
                    f"{path} does not contain '{expected_text}'"


# CLI runner for standalone testing
if __name__ == "__main__":
    import sys

    print(f"Testing pages at {BASE_URL}")
    print("=" * 60)

    # Quick test without pytest
    cookies = {}
    try:
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
            resp = client.post(
                "/auth/login",
                data={"email": "admin@dotmac.ng", "password": "admin123"},
                follow_redirects=False,
            )
            if resp.status_code in (302, 303, 307):
                cookies = dict(resp.cookies)
                print("Authentication: OK")
            else:
                print(f"Authentication: Failed ({resp.status_code})")
    except Exception as e:
        print(f"Authentication: Error - {e}")

    total_passed = 0
    total_failed = 0

    for module, routes in MODULE_ROUTES.items():
        print(f"\n{module.upper()}:")
        passed = 0
        failed = 0

        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, cookies=cookies) as client:
            for route in routes:
                url = substitute_path_params(route.path)
                try:
                    resp = client.get(url, follow_redirects=True)
                    if resp.status_code < 500:
                        passed += 1
                        print(f"  ✓ {route.path} -> {resp.status_code}")
                    else:
                        failed += 1
                        print(f"  ✗ {route.path} -> {resp.status_code}")
                except Exception as e:
                    failed += 1
                    print(f"  ✗ {route.path} -> {e}")

        total_passed += passed
        total_failed += failed
        print(f"  Summary: {passed}/{len(routes)} passed")

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {total_passed} passed, {total_failed} failed")
    sys.exit(0 if total_failed == 0 else 1)
