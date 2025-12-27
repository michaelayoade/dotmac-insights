#!/bin/bash

TOKEN="${API_TOKEN:-eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwibmFtZSI6IlRlc3QgVXNlciIsImlzX3N1cGVydXNlciI6dHJ1ZSwiY29tcGFueV9pZCI6MSwiZXhwIjoxNzY2OTAwMDIzLCJpYXQiOjE3NjY4MTM2MjN9.iG21XDYPUVBaZpZO6jVOWVxneTzEa50D37vc-LZzpAw}"
BASE="${API_BASE_URL:-http://localhost:8000}"

PASSED=0
FAILED=0
ERRORS=0

test_ep() {
    local endpoint="$1"
    local desc="$2"
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "${BASE}${endpoint}")
    if [ "$code" = "200" ] || [ "$code" = "201" ] || [ "$code" = "204" ]; then
        echo "✓ $desc - HTTP $code"
        PASSED=$((PASSED + 1))
    elif [ "$code" = "307" ]; then
        echo "↪ $desc - HTTP $code (Redirect)"
        PASSED=$((PASSED + 1))
    elif [ "$code" = "400" ]; then
        echo "⚠ $desc - HTTP $code (Bad Request)"
        PASSED=$((PASSED + 1))
    elif [ "$code" = "401" ] || [ "$code" = "403" ]; then
        echo "⚠ $desc - HTTP $code (Auth)"
        FAILED=$((FAILED + 1))
    elif [ "$code" = "404" ]; then
        echo "✗ $desc - HTTP $code (Not Found)"
        FAILED=$((FAILED + 1))
    elif [ "$code" = "422" ]; then
        echo "⚠ $desc - HTTP $code (Validation)"
        PASSED=$((PASSED + 1))
    elif [ "$code" = "500" ]; then
        echo "⚠ $desc - HTTP $code (Server Error)"
        ERRORS=$((ERRORS + 1))
    elif [ "$code" = "503" ]; then
        echo "⚠ $desc - HTTP $code (Service Unavailable)"
        FAILED=$((FAILED + 1))
    else
        echo "? $desc - HTTP $code"
        FAILED=$((FAILED + 1))
    fi
}

# Test endpoint that requires external service (503 is acceptable)
test_ep_external() {
    local endpoint="$1"
    local desc="$2"
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "${BASE}${endpoint}")
    if [ "$code" = "200" ] || [ "$code" = "201" ] || [ "$code" = "204" ]; then
        echo "✓ $desc - HTTP $code"
        PASSED=$((PASSED + 1))
    elif [ "$code" = "503" ]; then
        echo "○ $desc - HTTP $code (External service not configured - OK)"
        PASSED=$((PASSED + 1))
    elif [ "$code" = "500" ]; then
        echo "⚠ $desc - HTTP $code (Server Error)"
        ERRORS=$((ERRORS + 1))
    else
        echo "? $desc - HTTP $code"
        FAILED=$((FAILED + 1))
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DotMac API Endpoint Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Base URL: $BASE"
echo ""

echo "▶ HEALTH"
test_ep "/health" "Health Check"

echo ""
echo "▶ CRM MODULE"
test_ep "/api/crm/contacts/" "CRM Contacts"
test_ep "/api/crm/contacts/leads" "CRM Leads"
test_ep "/api/crm/contacts/customers" "CRM Customers"
test_ep "/api/crm/contacts/organizations" "CRM Organizations"
test_ep "/api/crm/opportunities/" "CRM Opportunities"
test_ep "/api/crm/activities/" "CRM Activities"
test_ep "/api/crm/pipeline/stages" "Pipeline Stages"
test_ep "/api/crm/pipeline/kanban" "Pipeline Kanban"

echo ""
echo "▶ ACCOUNTING - CORE"
test_ep "/api/accounting/dashboard" "Accounting Dashboard"
test_ep "/api/accounting/chart-of-accounts" "Chart of Accounts"
test_ep "/api/accounting/accounts" "Accounts List"
test_ep "/api/accounting/account-types" "Account Types"
test_ep "/api/accounting/journal-entries" "Journal Entries"
test_ep "/api/accounting/gl-entries" "GL Entries"
test_ep "/api/accounting/cost-centers" "Cost Centers"

echo ""
echo "▶ ACCOUNTING - RECEIVABLES & PAYABLES"
test_ep "/api/accounting/accounts-receivable" "Accounts Receivable"
test_ep "/api/accounting/accounts-payable?currency=NGN" "Accounts Payable"
test_ep "/api/accounting/ar-payments" "AR Payments"
test_ep "/api/accounting/ap-payments" "AP Payments"
test_ep "/api/accounting/credit-notes" "Credit Notes"
test_ep "/api/accounting/debit-notes" "Debit Notes"

echo ""
echo "▶ ACCOUNTING - BANKING"
test_ep "/api/accounting/bank-accounts" "Bank Accounts"
test_ep "/api/accounting/bank-transactions" "Bank Transactions"

echo ""
echo "▶ ACCOUNTING - FISCAL"
test_ep "/api/accounting/fiscal-years" "Fiscal Years"
test_ep "/api/accounting/fiscal-periods" "Fiscal Periods"
test_ep "/api/accounting/payment-terms" "Payment Terms"
test_ep "/api/accounting/modes-of-payment" "Payment Modes"

echo ""
echo "▶ ACCOUNTING - TAX"
test_ep "/api/accounting/tax-codes" "Tax Codes"
test_ep "/api/accounting/tax-categories" "Tax Categories"
test_ep "/api/accounting/tax-rules" "Tax Rules"
test_ep "/api/accounting/tax/dashboard" "Tax Dashboard"

echo ""
echo "▶ ACCOUNTING - REPORTS"
test_ep "/api/accounting/balance-sheet" "Balance Sheet"
test_ep "/api/accounting/income-statement" "Income Statement"
test_ep "/api/accounting/trial-balance" "Trial Balance"
test_ep "/api/accounting/cash-flow" "Cash Flow Statement"
test_ep "/api/accounting/general-ledger" "General Ledger"
test_ep "/api/accounting/receivables-aging" "Receivables Aging"
test_ep "/api/accounting/payables-aging?currency=NGN" "Payables Aging"
test_ep "/api/accounting/financial-ratios" "Financial Ratios"
test_ep "/api/accounting/equity-statement" "Equity Statement"

echo ""
echo "▶ FINANCE MODULE"
test_ep "/api/finance/dashboard" "Finance Dashboard"
test_ep "/api/finance/invoices" "Finance Invoices"
test_ep "/api/finance/payments" "Finance Payments"
test_ep "/api/finance/credit-notes" "Finance Credit Notes"

echo ""
echo "▶ HR MODULE"
test_ep "/api/hr/employees" "Employees"
test_ep "/api/hr/appraisals" "Appraisals"
test_ep "/api/hr/analytics/dashboard" "HR Analytics Dashboard"
test_ep "/api/hr/analytics/employees" "HR Employee Analytics"
test_ep "/api/hr/analytics/attendance-summary" "Attendance Summary"
test_ep "/api/hr/analytics/leave-balance" "Leave Balance Analytics"

echo ""
echo "▶ SUPPORT MODULE"
test_ep "/api/support/tickets" "Support Tickets"
test_ep "/api/support/agents" "Support Agents"
test_ep "/api/support/teams" "Support Teams"
test_ep "/api/support/sla/policies" "SLA Policies"
test_ep "/api/support/kb/articles" "KB Articles"
test_ep "/api/support/kb/categories" "KB Categories"
test_ep "/api/support/automation/rules" "Automation Rules"
test_ep "/api/support/csat/surveys" "CSAT Surveys"

echo ""
echo "▶ PROJECTS MODULE"
test_ep "/api/projects/projects" "Projects List"
test_ep "/api/projects/tasks" "All Tasks"
test_ep "/api/projects/dashboard" "Projects Dashboard"
test_ep "/api/projects/analytics/status-trend" "Project Status Trend"

echo ""
echo "▶ EXPENSES MODULE"
test_ep "/api/expenses/claims/" "Expense Claims"
test_ep "/api/expenses/categories/" "Expense Categories"
test_ep "/api/expenses/cards/" "Corporate Cards"
test_ep "/api/expenses/policies/" "Expense Policies"
test_ep "/api/expenses/cash-advances/" "Cash Advances"

echo ""
echo "▶ FIELD SERVICE MODULE"
test_ep "/api/field-service/orders" "Work Orders"
test_ep "/api/field-service/teams" "Field Teams"
test_ep "/api/field-service/technicians" "Technicians"

echo ""
echo "▶ INVENTORY MODULE"
test_ep "/api/inventory/items" "Inventory Items"
test_ep "/api/inventory/item-groups" "Item Groups"
test_ep "/api/inventory/warehouses" "Warehouses"
test_ep "/api/inventory/stock-entries" "Stock Entries"
test_ep "/api/inventory/stock-ledger" "Stock Ledger"

echo ""
echo "▶ PERFORMANCE MODULE"
test_ep "/api/performance/kpis" "KPIs"
test_ep "/api/performance/kras" "KRAs"
test_ep "/api/performance/periods" "Review Periods"
test_ep "/api/performance/templates" "Review Templates"
test_ep "/api/performance/scorecards" "Scorecards"

echo ""
echo "▶ INBOX/OMNI MODULE"
test_ep "/api/inbox/conversations" "Conversations"
test_ep "/api/inbox/contacts" "Inbox Contacts"

echo ""
echo "▶ PURCHASING MODULE"
test_ep "/api/purchasing/orders" "Purchase Orders"
test_ep "/api/purchasing/suppliers" "Suppliers"
test_ep "/api/purchasing/expenses" "Purchase Expenses"
test_ep "/api/purchasing/bills" "Bills"

echo ""
echo "▶ SALES MODULE"
test_ep "/api/sales/orders" "Sales Orders"
test_ep "/api/sales/quotations" "Quotations"
test_ep "/api/sales/invoices" "Sales Invoices"
test_ep "/api/sales/customer-groups" "Customer Groups"

echo ""
echo "▶ ADMIN & SETTINGS"
test_ep "/api/admin/users" "Admin Users"
test_ep "/api/admin/settings" "Admin Settings"
test_ep "/api/admin/sync/schedules" "Sync Schedules"
test_ep "/api/books/settings" "Books Settings"
test_ep "/api/assets/settings" "Asset Settings"

echo ""
echo "▶ ANALYTICS & DASHBOARDS"
test_ep "/api/dashboards/customers" "Customers Dashboard"
test_ep "/api/dashboards/hr" "HR Dashboard"
test_ep "/api/dashboards/projects" "Projects Dashboard"
test_ep "/api/insights/churn-risk" "Churn Risk"
test_ep "/api/v1/analytics/customers" "Customer Analytics"

echo ""
echo "▶ WORKFLOW TASKS"
test_ep "/api/v1/workflow-tasks/my-tasks" "My Workflow Tasks"
test_ep "/api/v1/workflow-tasks/my-tasks/summary" "Task Summary"

echo ""
echo "▶ SYNC & INTEGRATIONS"
test_ep "/api/sync/status" "Sync Status"

echo ""
echo "▶ PAYMENT INTEGRATIONS"
test_ep_external "/api/integrations/banks/" "Banks List (Paystack/Flutterwave)"
test_ep "/api/integrations/payments/" "Payments List"
test_ep_external "/api/integrations/transfers/" "Transfers List (Paystack/Flutterwave)"
test_ep_external "/api/integrations/openbanking/accounts" "OpenBanking Accounts (Mono)"
test_ep "/api/integrations/webhooks/events" "Webhook Events"
test_ep "/api/integrations/webhooks/providers" "Webhook Providers"

echo ""
echo "▶ DATA EXPLORER"
test_ep "/api/explore/tables" "Available Tables"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Passed:  $PASSED"
echo "Failed:  $FAILED"
echo "Errors:  $ERRORS (500 Server Errors)"
TOTAL=$((PASSED + FAILED + ERRORS))
if [ $TOTAL -gt 0 ]; then
    RATE=$((PASSED * 100 / TOTAL))
    echo "Pass Rate: ${RATE}%"
fi
echo ""
echo "Legend:"
echo "  ✓ = Success (200/201/204)"
echo "  ○ = External service not configured (503 - OK)"
echo "  ↪ = Redirect (307)"
echo "  ⚠ = Warning (400/422/500)"
echo "  ✗ = Failed (404/401/403)"
