#!/bin/bash

# =============================================================================
# DotMac Insights API Test Script
# Tests all major API endpoints using curl
# =============================================================================

set -e

# Configuration
BASE_URL="${API_BASE_URL:-http://localhost:8000}"
TOKEN="${API_TOKEN:-}"
VERBOSE="${VERBOSE:-false}"
TEST_ONLY="${TEST_ONLY:-}"  # Filter to specific module

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
SKIPPED=0

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_section() {
    echo ""
    echo -e "${YELLOW}▶ $1${NC}"
    echo -e "${YELLOW}─────────────────────────────────────────────────────────────────────────${NC}"
}

# Test an endpoint
# Usage: test_endpoint "METHOD" "ENDPOINT" "DESCRIPTION" "EXPECTED_CODES" ["DATA"]
test_endpoint() {
    local method="$1"
    local endpoint="$2"
    local description="$3"
    local expected_codes="$4"
    local data="${5:-}"

    local url="${BASE_URL}${endpoint}"
    local curl_opts="-s -w '\n%{http_code}' -H 'Content-Type: application/json'"

    if [ -n "$TOKEN" ]; then
        curl_opts="$curl_opts -H 'Authorization: Bearer $TOKEN'"
    fi

    case "$method" in
        GET)
            response=$(curl $curl_opts "$url" 2>&1) || true
            ;;
        POST)
            if [ -n "$data" ]; then
                response=$(curl $curl_opts -X POST -d "$data" "$url" 2>&1) || true
            else
                response=$(curl $curl_opts -X POST "$url" 2>&1) || true
            fi
            ;;
        PATCH)
            if [ -n "$data" ]; then
                response=$(curl $curl_opts -X PATCH -d "$data" "$url" 2>&1) || true
            else
                response=$(curl $curl_opts -X PATCH "$url" 2>&1) || true
            fi
            ;;
        DELETE)
            response=$(curl $curl_opts -X DELETE "$url" 2>&1) || true
            ;;
    esac

    # Extract status code (last line)
    http_code=$(echo "$response" | tail -n1 | tr -d "'")
    body=$(echo "$response" | sed '$d')

    # Check if status code is in expected codes
    local passed=false
    IFS=',' read -ra CODES <<< "$expected_codes"
    for code in "${CODES[@]}"; do
        if [ "$http_code" = "$code" ]; then
            passed=true
            break
        fi
    done

    if [ "$passed" = true ]; then
        echo -e "  ${GREEN}✓${NC} [$method] $endpoint - $description (HTTP $http_code)"
        ((PASSED++))
    else
        echo -e "  ${RED}✗${NC} [$method] $endpoint - $description"
        echo -e "    ${RED}Expected: $expected_codes, Got: $http_code${NC}"
        if [ "$VERBOSE" = "true" ]; then
            echo -e "    ${RED}Response: ${body:0:200}${NC}"
        fi
        ((FAILED++))
    fi
}

should_test() {
    local module="$1"
    if [ -z "$TEST_ONLY" ]; then
        return 0
    fi
    if [[ "$TEST_ONLY" == *"$module"* ]]; then
        return 0
    fi
    return 1
}

# =============================================================================
# Health & System Endpoints
# =============================================================================
test_health() {
    if ! should_test "health"; then return; fi
    print_section "Health & System"

    test_endpoint "GET" "/health" "Health check" "200"
    test_endpoint "GET" "/api/health" "API Health check" "200,404"
}

# =============================================================================
# Authentication (Public endpoints)
# =============================================================================
test_auth() {
    if ! should_test "auth"; then return; fi
    print_section "Authentication"

    # These should work without auth
    test_endpoint "GET" "/api/auth/me" "Current user info" "200,401"
}

# =============================================================================
# CRM Module
# =============================================================================
test_crm() {
    if ! should_test "crm"; then return; fi
    print_section "CRM - Contacts"

    test_endpoint "GET" "/api/v1/crm/contacts" "List contacts" "200,401,403"
    test_endpoint "GET" "/api/v1/crm/contacts?skip=0&limit=10" "List contacts (paginated)" "200,401,403"

    print_section "CRM - Leads"
    test_endpoint "GET" "/api/v1/crm/leads" "List leads" "200,401,403"

    print_section "CRM - Opportunities"
    test_endpoint "GET" "/api/v1/crm/opportunities" "List opportunities" "200,401,403"

    print_section "CRM - Activities"
    test_endpoint "GET" "/api/v1/crm/activities" "List activities" "200,401,403"

    print_section "CRM - Pipeline"
    test_endpoint "GET" "/api/v1/crm/pipeline/stages" "Get pipeline stages" "200,401,403"
    test_endpoint "GET" "/api/v1/crm/pipeline/kanban" "Get kanban view" "200,401,403"
}

# =============================================================================
# Accounting Module
# =============================================================================
test_accounting() {
    if ! should_test "accounting"; then return; fi
    print_section "Accounting - Dashboard"

    test_endpoint "GET" "/api/v1/accounting/dashboard" "Accounting dashboard" "200,401,403"

    print_section "Accounting - Reports"
    test_endpoint "GET" "/api/v1/accounting/reports?report_type=trial-balance" "Trial Balance" "200,401,403,422"
    test_endpoint "GET" "/api/v1/accounting/reports?report_type=balance-sheet" "Balance Sheet" "200,401,403,422"
    test_endpoint "GET" "/api/v1/accounting/reports?report_type=income-statement" "Income Statement" "200,401,403,422"

    print_section "Accounting - Ledger"
    test_endpoint "GET" "/api/v1/accounting/ledger" "Chart of Accounts" "200,401,403"
    test_endpoint "GET" "/api/v1/accounting/ledger/accounts" "List accounts" "200,401,403"

    print_section "Accounting - Journal Entries"
    test_endpoint "GET" "/api/v1/accounting/journal-entries" "List journal entries" "200,401,403"

    print_section "Accounting - Receivables"
    test_endpoint "GET" "/api/v1/accounting/receivables" "List receivables" "200,401,403"
    test_endpoint "GET" "/api/v1/accounting/receivables/aging" "AR Aging" "200,401,403"

    print_section "Accounting - Payables"
    test_endpoint "GET" "/api/v1/accounting/payables" "List payables" "200,401,403"
    test_endpoint "GET" "/api/v1/accounting/payables/aging" "AP Aging" "200,401,403"

    print_section "Accounting - Banking"
    test_endpoint "GET" "/api/v1/accounting/banking/accounts" "Bank accounts" "200,401,403"
    test_endpoint "GET" "/api/v1/accounting/banking/transactions" "Bank transactions" "200,401,403"

    print_section "Accounting - Fiscal"
    test_endpoint "GET" "/api/v1/accounting/fiscal/years" "Fiscal years" "200,401,403"
    test_endpoint "GET" "/api/v1/accounting/fiscal/periods" "Fiscal periods" "200,401,403"

    print_section "Accounting - Payments"
    test_endpoint "GET" "/api/v1/accounting/payment-terms" "Payment terms" "200,401,403"
    test_endpoint "GET" "/api/v1/accounting/payment-modes" "Payment modes" "200,401,403"

    print_section "Accounting - Tax"
    test_endpoint "GET" "/api/v1/accounting/tax-codes" "Tax codes" "200,401,403"
}

# =============================================================================
# Finance Module
# =============================================================================
test_finance() {
    if ! should_test "finance"; then return; fi
    print_section "Finance"

    test_endpoint "GET" "/api/finance/dashboard" "Finance dashboard" "200,401,403"
    test_endpoint "GET" "/api/finance/invoices" "List invoices" "200,401,403"
    test_endpoint "GET" "/api/finance/payments" "List payments" "200,401,403"
    test_endpoint "GET" "/api/finance/credit-notes" "List credit notes" "200,401,403"
    test_endpoint "GET" "/api/finance/analytics/revenue-trends" "Revenue trends" "200,401,403"
}

# =============================================================================
# HR Module
# =============================================================================
test_hr() {
    if ! should_test "hr"; then return; fi
    print_section "HR - Leave Management"

    test_endpoint "GET" "/api/v1/hr/leave" "Leave requests" "200,401,403"
    test_endpoint "GET" "/api/v1/hr/leave/types" "Leave types" "200,401,403"
    test_endpoint "GET" "/api/v1/hr/leave/balances" "Leave balances" "200,401,403"

    print_section "HR - Attendance"
    test_endpoint "GET" "/api/v1/hr/attendance" "Attendance records" "200,401,403"

    print_section "HR - Payroll"
    test_endpoint "GET" "/api/v1/hr/payroll" "Payroll runs" "200,401,403"
    test_endpoint "GET" "/api/v1/hr/payroll/payslips" "Payslips" "200,401,403"

    print_section "HR - Recruitment"
    test_endpoint "GET" "/api/v1/hr/recruitment/jobs" "Job postings" "200,401,403"
    test_endpoint "GET" "/api/v1/hr/recruitment/applications" "Applications" "200,401,403"

    print_section "HR - Training"
    test_endpoint "GET" "/api/v1/hr/training/programs" "Training programs" "200,401,403"

    print_section "HR - Analytics"
    test_endpoint "GET" "/api/v1/hr/analytics" "HR analytics" "200,401,403"

    print_section "HR - Masters"
    test_endpoint "GET" "/api/v1/hr/masters/departments" "Departments" "200,401,403"
    test_endpoint "GET" "/api/v1/hr/masters/designations" "Designations" "200,401,403"
}

# =============================================================================
# Support Module
# =============================================================================
test_support() {
    if ! should_test "support"; then return; fi
    print_section "Support - Tickets"

    test_endpoint "GET" "/api/v1/support/tickets" "List tickets" "200,401,403"
    test_endpoint "GET" "/api/v1/support/tickets?status=open" "Open tickets" "200,401,403"

    print_section "Support - Agents"
    test_endpoint "GET" "/api/v1/support/agents" "List agents" "200,401,403"
    test_endpoint "GET" "/api/v1/support/agents/teams" "Support teams" "200,401,403"

    print_section "Support - SLA"
    test_endpoint "GET" "/api/v1/support/sla/policies" "SLA policies" "200,401,403"

    print_section "Support - Knowledge Base"
    test_endpoint "GET" "/api/v1/support/knowledge-base/articles" "KB articles" "200,401,403"
    test_endpoint "GET" "/api/v1/support/knowledge-base/categories" "KB categories" "200,401,403"

    print_section "Support - Analytics"
    test_endpoint "GET" "/api/v1/support/analytics" "Support analytics" "200,401,403"

    print_section "Support - Automation"
    test_endpoint "GET" "/api/v1/support/automation/rules" "Automation rules" "200,401,403"

    print_section "Support - Canned Responses"
    test_endpoint "GET" "/api/v1/support/canned-responses" "Canned responses" "200,401,403"
}

# =============================================================================
# Projects Module
# =============================================================================
test_projects() {
    if ! should_test "projects"; then return; fi
    print_section "Projects"

    test_endpoint "GET" "/api/v1/projects" "List projects" "200,401,403"
    test_endpoint "GET" "/api/v1/projects/templates" "Project templates" "200,401,403"
    test_endpoint "GET" "/api/v1/projects/analytics" "Project analytics" "200,401,403"

    print_section "Tasks"
    test_endpoint "GET" "/api/v1/projects/tasks" "List all tasks" "200,401,403"
}

# =============================================================================
# Expenses Module
# =============================================================================
test_expenses() {
    if ! should_test "expenses"; then return; fi
    print_section "Expenses"

    test_endpoint "GET" "/api/v1/expenses" "List expenses" "200,401,403"
    test_endpoint "GET" "/api/v1/expenses/claims" "Expense claims" "200,401,403"
    test_endpoint "GET" "/api/v1/expenses/categories" "Expense categories" "200,401,403"
    test_endpoint "GET" "/api/v1/expenses/policies" "Expense policies" "200,401,403"

    print_section "Expenses - Cards"
    test_endpoint "GET" "/api/v1/expenses/cards" "Corporate cards" "200,401,403"

    print_section "Expenses - Cash Advances"
    test_endpoint "GET" "/api/v1/expenses/cash-advances" "Cash advances" "200,401,403"

    print_section "Expenses - Analytics"
    test_endpoint "GET" "/api/v1/expenses/analytics" "Expense analytics" "200,401,403"
}

# =============================================================================
# Tax Module
# =============================================================================
test_tax() {
    if ! should_test "tax"; then return; fi
    print_section "Tax - Dashboard"

    test_endpoint "GET" "/api/v1/tax/dashboard" "Tax dashboard" "200,401,403"

    print_section "Tax - VAT"
    test_endpoint "GET" "/api/v1/tax/vat" "VAT records" "200,401,403"
    test_endpoint "GET" "/api/v1/tax/vat/dashboard" "VAT dashboard" "200,401,403"

    print_section "Tax - WHT"
    test_endpoint "GET" "/api/v1/tax/withholding" "WHT records" "200,401,403"

    print_section "Tax - PAYE"
    test_endpoint "GET" "/api/v1/tax/paye" "PAYE records" "200,401,403"

    print_section "Tax - Filing"
    test_endpoint "GET" "/api/v1/tax/filings" "Tax filings" "200,401,403"

    print_section "Tax - Certificates"
    test_endpoint "GET" "/api/v1/tax/certificates" "Tax certificates" "200,401,403"
}

# =============================================================================
# Field Service Module
# =============================================================================
test_field_service() {
    if ! should_test "field"; then return; fi
    print_section "Field Service"

    test_endpoint "GET" "/api/v1/field-service/orders" "Work orders" "200,401,403"
    test_endpoint "GET" "/api/v1/field-service/teams" "Field teams" "200,401,403"
    test_endpoint "GET" "/api/v1/field-service/scheduling" "Scheduling" "200,401,403"
    test_endpoint "GET" "/api/v1/field-service/analytics" "Field analytics" "200,401,403"
}

# =============================================================================
# Inventory Module
# =============================================================================
test_inventory() {
    if ! should_test "inventory"; then return; fi
    print_section "Inventory"

    test_endpoint "GET" "/api/v1/inventory/items" "Items" "200,401,403"
    test_endpoint "GET" "/api/v1/inventory/warehouses" "Warehouses" "200,401,403"
    test_endpoint "GET" "/api/v1/inventory/stock" "Stock levels" "200,401,403"
    test_endpoint "GET" "/api/v1/inventory/stock-entries" "Stock entries" "200,401,403"
}

# =============================================================================
# Performance Module
# =============================================================================
test_performance() {
    if ! should_test "performance"; then return; fi
    print_section "Performance Management"

    test_endpoint "GET" "/api/v1/performance/kpis" "KPIs" "200,401,403"
    test_endpoint "GET" "/api/v1/performance/kras" "KRAs" "200,401,403"
    test_endpoint "GET" "/api/v1/performance/periods" "Review periods" "200,401,403"
    test_endpoint "GET" "/api/v1/performance/reviews" "Reviews" "200,401,403"
    test_endpoint "GET" "/api/v1/performance/templates" "Templates" "200,401,403"
    test_endpoint "GET" "/api/v1/performance/analytics" "Performance analytics" "200,401,403"
}

# =============================================================================
# Inbox / Omnichannel Module
# =============================================================================
test_inbox() {
    if ! should_test "inbox"; then return; fi
    print_section "Omnichannel Inbox"

    test_endpoint "GET" "/api/v1/inbox/conversations" "Conversations" "200,401,403"
    test_endpoint "GET" "/api/v1/inbox/contacts" "Inbox contacts" "200,401,403"
    test_endpoint "GET" "/api/v1/inbox/routing/rules" "Routing rules" "200,401,403"
    test_endpoint "GET" "/api/v1/inbox/analytics" "Inbox analytics" "200,401,403"
}

# =============================================================================
# Purchasing Module
# =============================================================================
test_purchasing() {
    if ! should_test "purchasing"; then return; fi
    print_section "Purchasing"

    test_endpoint "GET" "/api/purchasing/orders" "Purchase orders" "200,401,403"
    test_endpoint "GET" "/api/purchasing/suppliers" "Suppliers" "200,401,403"
    test_endpoint "GET" "/api/purchasing/expenses" "Expenses" "200,401,403"
}

# =============================================================================
# Sales Module
# =============================================================================
test_sales() {
    if ! should_test "sales"; then return; fi
    print_section "Sales"

    test_endpoint "GET" "/api/sales/orders" "Sales orders" "200,401,403"
    test_endpoint "GET" "/api/sales/quotations" "Quotations" "200,401,403"
    test_endpoint "GET" "/api/sales/invoices" "Invoices" "200,401,403"
}

# =============================================================================
# Customers Module
# =============================================================================
test_customers() {
    if ! should_test "customers"; then return; fi
    print_section "Customers"

    test_endpoint "GET" "/api/customers" "List customers" "200,401,403"
    test_endpoint "GET" "/api/customers?skip=0&limit=10" "Customers (paginated)" "200,401,403"
}

# =============================================================================
# Contacts Module (Unified)
# =============================================================================
test_contacts() {
    if ! should_test "contacts"; then return; fi
    print_section "Contacts (Unified)"

    test_endpoint "GET" "/api/v1/contacts" "List contacts" "200,401,403"
    test_endpoint "GET" "/api/v1/contacts/lists" "Contact lists" "200,401,403"
    test_endpoint "GET" "/api/v1/contacts/analytics" "Contact analytics" "200,401,403"
}

# =============================================================================
# Admin Module
# =============================================================================
test_admin() {
    if ! should_test "admin"; then return; fi
    print_section "Admin"

    test_endpoint "GET" "/api/v1/admin/users" "Admin users" "200,401,403"
    test_endpoint "GET" "/api/v1/admin/settings" "Admin settings" "200,401,403"
    test_endpoint "GET" "/api/v1/admin/audit-log" "Audit log" "200,401,403"
}

# =============================================================================
# Settings Modules
# =============================================================================
test_settings() {
    if ! should_test "settings"; then return; fi
    print_section "Settings"

    test_endpoint "GET" "/api/v1/settings" "General settings" "200,401,403"
    test_endpoint "GET" "/api/v1/books-settings" "Books settings" "200,401,403"
    test_endpoint "GET" "/api/v1/hr-settings" "HR settings" "200,401,403"
    test_endpoint "GET" "/api/v1/support-settings" "Support settings" "200,401,403"
    test_endpoint "GET" "/api/v1/payroll-config" "Payroll config" "200,401,403"
}

# =============================================================================
# Analytics & Insights
# =============================================================================
test_analytics() {
    if ! should_test "analytics"; then return; fi
    print_section "Analytics & Insights"

    test_endpoint "GET" "/api/v1/analytics" "General analytics" "200,401,403"
    test_endpoint "GET" "/api/v1/insights" "Insights" "200,401,403"
    test_endpoint "GET" "/api/v1/dashboards" "Dashboards" "200,401,403"
}

# =============================================================================
# Sync & Integration
# =============================================================================
test_sync() {
    if ! should_test "sync"; then return; fi
    print_section "Sync & Integration"

    test_endpoint "GET" "/api/v1/sync/status" "Sync status" "200,401,403"
    test_endpoint "GET" "/api/v1/integrations/banks" "Bank integrations" "200,401,403"
}

# =============================================================================
# Workflow Tasks
# =============================================================================
test_workflow() {
    if ! should_test "workflow"; then return; fi
    print_section "Workflow Tasks"

    test_endpoint "GET" "/api/workflow-tasks" "Workflow tasks" "200,401,403"
    test_endpoint "GET" "/api/workflow-tasks/pending" "Pending tasks" "200,401,403"
}

# =============================================================================
# Notifications
# =============================================================================
test_notifications() {
    if ! should_test "notifications"; then return; fi
    print_section "Notifications"

    test_endpoint "GET" "/api/notifications" "Notifications" "200,401,403"
    test_endpoint "GET" "/api/notifications/webhooks" "Webhooks" "200,401,403"
}

# =============================================================================
# Main Execution
# =============================================================================

print_header "DotMac Insights API Test Suite"
echo ""
echo "Configuration:"
echo "  Base URL: $BASE_URL"
echo "  Token: ${TOKEN:0:20}${TOKEN:+...}"
echo "  Verbose: $VERBOSE"
echo "  Test Only: ${TEST_ONLY:-all modules}"

# Check if server is reachable
echo ""
echo "Checking server connectivity..."
if ! curl -s --connect-timeout 5 "$BASE_URL/health" > /dev/null 2>&1; then
    if ! curl -s --connect-timeout 5 "$BASE_URL" > /dev/null 2>&1; then
        echo -e "${RED}Error: Cannot connect to $BASE_URL${NC}"
        echo "Make sure the server is running and accessible."
        exit 1
    fi
fi
echo -e "${GREEN}Server is reachable${NC}"

# Run all tests
test_health
test_auth
test_crm
test_accounting
test_finance
test_hr
test_support
test_projects
test_expenses
test_tax
test_field_service
test_inventory
test_performance
test_inbox
test_purchasing
test_sales
test_customers
test_contacts
test_admin
test_settings
test_analytics
test_sync
test_workflow
test_notifications

# Summary
print_header "Test Summary"
echo ""
echo -e "  ${GREEN}Passed:${NC}  $PASSED"
echo -e "  ${RED}Failed:${NC}  $FAILED"
echo -e "  ${YELLOW}Skipped:${NC} $SKIPPED"
echo ""

TOTAL=$((PASSED + FAILED))
if [ $TOTAL -gt 0 ]; then
    PASS_RATE=$((PASSED * 100 / TOTAL))
    echo -e "  Pass Rate: ${PASS_RATE}%"
fi

echo ""
if [ $FAILED -gt 0 ]; then
    echo -e "${YELLOW}Some tests failed. Use VERBOSE=true for more details.${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
fi
