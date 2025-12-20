# Dotmac BOS - User Journey Documentation

## Table of Contents

1. [Overview](#overview)
2. [Sales & CRM Journeys](#1-sales--crm-journeys)
3. [Finance & Accounting Journeys](#2-finance--accounting-journeys)
4. [HR & Payroll Journeys](#3-hr--payroll-journeys)
5. [Expense Management Journeys](#4-expense-management-journeys)
6. [Support & Helpdesk Journeys](#5-support--helpdesk-journeys)
7. [Inbox & Communication Journeys](#6-inbox--communication-journeys)
8. [Inventory & Stock Journeys](#7-inventory--stock-journeys)
9. [Purchasing & AP Journeys](#8-purchasing--ap-journeys)
10. [Field Service Journeys](#9-field-service-journeys)
11. [Performance Management Journeys](#10-performance-management-journeys)
12. [Admin & Settings Journeys](#11-admin--settings-journeys)
13. [Integration & Sync Journeys](#12-integration--sync-journeys)

---

## Overview

This document describes all end-to-end user journeys in the Dotmac Business Operating System (BOS). Each journey represents a complete workflow from initiation to completion, including:
- **Entry Points**: How users start the journey
- **Steps**: Sequential actions taken
- **Pages Involved**: Frontend routes visited
- **API Endpoints**: Backend calls made
- **Outcomes**: Expected results and side effects

### User Roles & Permissions

| Role | Scopes | Access Level |
|------|--------|--------------|
| Super Admin | `*` | Full system access |
| Admin | `admin:read`, `admin:write` | Settings, webhooks, roles |
| Finance Manager | `accounting:*`, `payments:*` | Full accounting access |
| HR Manager | `hr:read`, `hr:write` | People & payroll |
| Sales Rep | `customers:read`, `customers:write` | CRM & sales |
| Support Agent | `customers:read`, `tickets:*` | Helpdesk access |
| Read-Only | `analytics:read`, `explore:read` | Dashboard viewing |

---

## 1. Sales & CRM Journeys

### 1.1 Lead to Customer Conversion

**Goal**: Convert a potential lead into a paying customer through the sales funnel.

**Entry Points**:
- Manual lead creation via `/sales/leads/new`
- Lead capture from website forms (via webhook)
- Import from external CRM (Zoho import)
- Inbox conversation conversion

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Lead Capture   │ -> │  Qualification  │ -> │   Opportunity   │
│                 │    │                 │    │                 │
│ /sales/leads    │    │ /sales/leads/   │    │ /sales/         │
│ /sales/leads/new│    │ [id]            │    │ opportunities   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Customer     │ <- │   Quotation     │ <- │     Deal        │
│                 │    │                 │    │   Negotiation   │
│ /sales/         │    │ /sales/         │    │ /sales/pipeline │
│ customers/[id]  │    │ quotations      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Lead Capture**
   - Page: `/sales/leads/new`
   - API: `POST /api/crm/leads`
   - Fields: Name, email, phone, source, company
   - Triggers: Lead scoring automation

2. **Lead Qualification**
   - Page: `/sales/leads/[id]`
   - API: `PATCH /api/crm/leads/{id}`
   - Actions: Update status, add notes, schedule follow-up
   - Scoring: Automatic lead score calculation

3. **Opportunity Creation**
   - Page: `/sales/opportunities/new`
   - API: `POST /api/crm/opportunities`
   - Fields: Deal value, expected close date, probability
   - Links to lead record

4. **Pipeline Management**
   - Page: `/sales/pipeline`
   - API: `GET /api/crm/pipeline`
   - Kanban board: Drag-and-drop stage progression
   - Stages: Prospecting → Qualification → Proposal → Negotiation → Closed

5. **Quotation**
   - Page: `/sales/quotations/new`
   - API: `POST /api/sales/quotations`
   - Items: Products/services with pricing
   - Actions: Send to customer, track opens

6. **Customer Conversion**
   - API: `POST /api/contacts`
   - Creates unified contact record
   - Status: Lead → Customer
   - Triggers: Welcome email, account setup

**Side Effects**:
- Contact created in unified contacts module
- Activity log updated
- Sales analytics updated
- Notifications to sales manager

---

### 1.2 Sales Order to Invoice

**Goal**: Process a sales order and generate customer invoice.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Sales Order    │ -> │    Delivery     │ -> │    Invoice      │
│                 │    │                 │    │                 │
│ /sales/orders   │    │ (Inventory      │    │ /sales/invoices │
│ /orders/new     │    │  Stock Issue)   │    │ /invoices/new   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Complete     │ <- │   Allocation    │ <- │    Payment      │
│                 │    │                 │    │                 │
│ Order Closed    │    │ Payment         │    │ /sales/payments │
│                 │    │ Allocation      │    │ /payments/new   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Create Sales Order**
   - Page: `/sales/orders/new`
   - API: `POST /api/sales/orders`
   - Fields: Customer, items, quantities, pricing, terms
   - Status: Draft → Submitted

2. **Order Approval** (if required)
   - API: `POST /api/sales/orders/{id}/approve`
   - Workflow: Manager approval for high-value orders

3. **Stock Issue** (for physical goods)
   - Triggered automatically or manually
   - API: `POST /api/inventory/stock-entries`
   - Type: Material Issue
   - Reduces warehouse stock

4. **Invoice Generation**
   - Page: `/sales/invoices/new`
   - API: `POST /api/accounting/invoices`
   - Auto-populated from sales order
   - Status: Draft → Posted

5. **Invoice Posting**
   - API: `POST /api/accounting/invoices/{id}/post`
   - Creates GL entries (Debit: Receivables, Credit: Revenue)
   - Creates tax entries (VAT, WHT)

6. **Payment Receipt**
   - Page: `/sales/payments/new`
   - API: `POST /api/accounting/payments/incoming`
   - Methods: Bank transfer, card, cash, gateway

7. **Payment Allocation**
   - API: `POST /api/accounting/allocations`
   - Links payment to invoice(s)
   - Reduces receivables balance

**GL Impact**:
```
Invoice Posting:
  DR Accounts Receivable    NGN 115,000
    CR Sales Revenue                    NGN 100,000
    CR VAT Payable                      NGN  7,500
    CR WHT Receivable                   NGN  7,500

Payment Receipt:
  DR Bank Account           NGN 115,000
    CR Accounts Receivable              NGN 115,000
```

---

### 1.3 Customer Credit Management

**Goal**: Manage customer credit limits and collection.

**Journey Flow**:

1. **Credit Limit Setup**
   - Page: `/books/accounts-receivable/credit`
   - API: `PATCH /api/contacts/{id}`
   - Fields: Credit limit, payment terms, credit hold threshold

2. **Credit Utilization Monitoring**
   - Page: `/books/accounts-receivable`
   - API: `GET /api/accounting/receivables/summary`
   - Shows current outstanding vs credit limit

3. **Credit Block Trigger**
   - Automatic when: Outstanding > Credit Limit
   - API: `POST /api/contacts/{id}/credit-hold`
   - Blocks new sales orders

4. **Dunning Process**
   - Page: `/books/accounts-receivable/dunning`
   - API: `POST /api/accounting/dunning/run`
   - Sends staged reminder emails (30, 60, 90 days)

5. **Collection**
   - Record payment via `/sales/payments/new`
   - Credit hold automatically released

---

## 2. Finance & Accounting Journeys

### 2.1 Chart of Accounts Setup

**Goal**: Configure the general ledger account structure.

**Entry Point**: `/books/chart-of-accounts`

**Steps**:

1. **View Account Tree**
   - Page: `/books/chart-of-accounts`
   - API: `GET /api/accounting/accounts`
   - Hierarchical tree view

2. **Create Account**
   - API: `POST /api/accounting/accounts`
   - Fields: Account code, name, type, parent account
   - Types: Asset, Liability, Equity, Income, Expense

3. **Configure Account Properties**
   - Page: `/books/chart-of-accounts/[id]`
   - Fields: Currency, cost center, tax applicability

---

### 2.2 Journal Entry Workflow

**Goal**: Record manual journal entries with approval workflow.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Draft Entry    │ -> │    Review       │ -> │    Posted       │
│                 │    │                 │    │                 │
│ /books/journal- │    │ Approval        │    │ GL Updated      │
│ entries/new     │    │ Workflow        │    │ Trial Balance   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Create Journal Entry**
   - Page: `/books/journal-entries/new`
   - API: `POST /api/accounting/journal-entries`
   - Required: Balanced debits and credits
   - Validation via `je_validator.py` service

2. **Validation Rules**:
   - Debits must equal credits
   - Valid account codes
   - Period must be open
   - Supporting documents attached

3. **Approval** (if configured)
   - API: `POST /api/accounting/journal-entries/{id}/approve`
   - Based on amount thresholds

4. **Posting**
   - API: `POST /api/accounting/journal-entries/{id}/post`
   - Creates GL entries
   - Updates trial balance

**GL Entry Created**:
```json
{
  "entries": [
    {"account": "5000", "debit": 50000, "credit": 0},
    {"account": "2100", "debit": 0, "credit": 50000}
  ],
  "narration": "Office rent for January 2025",
  "posting_date": "2025-01-31"
}
```

---

### 2.3 Bank Reconciliation

**Goal**: Match bank transactions with accounting records.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Import Bank    │ -> │    Matching     │ -> │  Reconciled     │
│  Statement      │    │                 │    │                 │
│ /books/bank-    │    │ Auto + Manual   │    │ Balance         │
│ transactions/   │    │ Match Rules     │    │ Verified        │
│ import          │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Statement Import**
   - Page: `/books/bank-transactions/import`
   - API: `POST /api/accounting/bank/import`
   - Formats: CSV, OFX, QIF, or Open Banking API
   - Service: `bank_reconciliation.py`

2. **Auto-Matching**
   - API: `POST /api/accounting/bank/auto-match`
   - Matching criteria: Amount, date, reference
   - Service: `transaction_matching_service.py`

3. **Manual Matching**
   - Page: `/books/bank-transactions`
   - API: `POST /api/accounting/bank/match`
   - User selects transaction pairs

4. **Reconciliation Completion**
   - API: `POST /api/accounting/bank/reconcile`
   - Locks matched transactions
   - Creates reconciliation statement

---

### 2.4 Financial Reporting

**Goal**: Generate standard financial statements.

**Reports Available**:

| Report | Page | API | Description |
|--------|------|-----|-------------|
| Balance Sheet | `/books/balance-sheet` | `GET /api/accounting/balance-sheet` | Assets, Liabilities, Equity |
| Income Statement | `/books/income-statement` | `GET /api/accounting/income-statement` | Revenue, Expenses, Profit |
| Cash Flow | `/books/cash-flow` | `GET /api/accounting/cash-flow` | Operating, Investing, Financing |
| Trial Balance | `/books/trial-balance` | `GET /api/accounting/trial-balance` | All account balances |
| General Ledger | `/books/general-ledger` | `GET /api/accounting/ledger` | Transaction details |

**Filters**:
- Date range
- Fiscal period
- Cost center
- Currency

---

### 2.5 Tax Compliance (Nigerian)

**Goal**: Manage Nigerian tax obligations (VAT, WHT, PAYE, CIT).

**Journey Flow**:

1. **Tax Configuration**
   - Page: `/books/tax/settings`
   - API: `GET /api/tax/configuration`
   - Configure tax codes, rates, accounts

2. **VAT Processing**
   - Page: `/books/tax/vat`
   - API: `GET /api/tax/vat/summary`
   - Input VAT vs Output VAT calculation
   - Monthly filing preparation

3. **Withholding Tax**
   - Page: `/books/tax/wht`
   - API: `GET /api/tax/wht/report`
   - WHT on vendor payments
   - Credit notes for customer WHT

4. **PAYE (Employee Tax)**
   - Page: `/books/tax/paye`
   - Linked to payroll processing
   - Monthly remittance tracking

5. **E-Invoice Generation**
   - Page: `/books/tax/einvoice`
   - API: `POST /api/tax/einvoice/generate`
   - FIRS BIS 3.0 compliance
   - QR code generation

6. **Filing Calendar**
   - Page: `/books/tax/filing`
   - Deadline tracking and reminders

---

### 2.6 Payment Gateway Integration

**Goal**: Process online payments via Paystack/Flutterwave.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Customer       │ -> │    Gateway      │ -> │    Webhook      │
│  Initiates      │    │   Processing    │    │   Callback      │
│                 │    │                 │    │                 │
│ Payment Link    │    │ Paystack/       │    │ POST /webhooks/ │
│ or Checkout     │    │ Flutterwave     │    │ inbound/paystack│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Complete     │ <- │   Allocation    │ <- │    Payment      │
│                 │    │                 │    │   Recorded      │
│ Invoice Paid    │    │ Auto-allocate   │    │ /books/gateway/ │
│                 │    │ to invoice      │    │ payments        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Generate Payment Link**
   - API: `POST /api/integrations/payments/initialize`
   - Creates transaction with provider

2. **Customer Payment**
   - Redirect to gateway checkout
   - Card/bank transfer/USSD

3. **Webhook Receipt**
   - Endpoint: `/api/webhooks/inbound/{provider}`
   - Service: `webhooks/processor.py`
   - Validates signature

4. **Transaction Recording**
   - API: Internal `GatewayTransaction` created
   - Status tracking: pending → success/failed

5. **Auto-Allocation**
   - Service: `payment_allocation_service.py`
   - Links to invoice reference
   - Creates AR payment

**Pages**:
- `/books/gateway/payments` - View transactions
- `/books/gateway/connections` - Open Banking setup

---

## 3. HR & Payroll Journeys

### 3.1 Employee Onboarding

**Goal**: Complete new employee setup from offer to first payroll.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Job Opening    │ -> │   Recruitment   │ -> │   Offer &       │
│                 │    │                 │    │   Acceptance    │
│ /hr/recruitment │    │ /hr/recruitment │    │                 │
│                 │    │ /[job_id]       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  First Payroll  │ <- │   Onboarding    │ <- │   Employee      │
│                 │    │   Tasks         │    │   Record        │
│ /hr/payroll     │    │                 │    │ /hr/employees   │
│                 │    │ /hr/lifecycle   │    │ /[id]           │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Create Job Opening**
   - Page: `/hr/recruitment`
   - API: `POST /api/hr/jobs`
   - Fields: Title, department, requirements, salary range

2. **Applicant Tracking**
   - API: `POST /api/hr/applicants`
   - Status: Applied → Screening → Interview → Offer

3. **Employee Record Creation**
   - API: `POST /api/hr/employees`
   - Fields: Personal info, bank details, tax ID (TIN)
   - Links to contact record

4. **Compensation Setup**
   - API: `PATCH /api/hr/employees/{id}/salary`
   - Base salary, allowances, deductions

5. **Onboarding Workflow**
   - Page: `/hr/lifecycle`
   - Checklist: IT setup, documentation, training

6. **Payroll Inclusion**
   - Employee added to next payroll run

---

### 3.2 Payroll Processing

**Goal**: Run monthly payroll and generate payslips.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Period Setup   │ -> │   Calculation   │ -> │    Review       │
│                 │    │                 │    │                 │
│ /hr/payroll     │    │ Engine runs     │    │ Preview totals  │
│ /settings       │    │ deductions      │    │ /hr/payroll/run │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Disbursement  │ <- │    Posting      │ <- │   Approval      │
│                 │    │                 │    │                 │
│ Bank payments   │    │ GL entries      │    │ Manager sign-off│
│ initiated       │    │ created         │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Configure Payroll Settings**
   - Page: `/hr/payroll/settings`
   - API: `GET/POST /api/hr/payroll/config`
   - Deduction rules: PAYE, Pension, NHF, loans

2. **Create Payroll Period**
   - API: `POST /api/hr/payroll/periods`
   - Month, year, payment date

3. **Run Payroll Calculation**
   - Page: `/hr/payroll/run`
   - API: `POST /api/hr/payroll/calculate`
   - Service: `payroll_engine.py`
   - Calculates per employee:
     - Gross earnings (base + allowances)
     - Statutory deductions (PAYE, pension, NHF)
     - Voluntary deductions (loans, advances)
     - Net pay

4. **PAYE Calculation** (Nigerian Tax)
   - Service: `nigerian_tax_service.py`
   - Annual tax computed monthly
   - Tax brackets applied

5. **Review & Approval**
   - Page: `/hr/payroll`
   - API: `POST /api/hr/payroll/{id}/approve`
   - Verify totals before posting

6. **Post Payroll**
   - API: `POST /api/hr/payroll/{id}/post`
   - Creates GL entries
   - Service: `document_posting.py`

7. **Generate Payslips**
   - Page: `/hr/payroll/payslips`
   - API: `GET /api/hr/payroll/payslips`
   - PDF download available

8. **Bank Disbursement**
   - Export payment file for bank
   - Or trigger via payment gateway

**GL Entries Created**:
```
Payroll Posting:
  DR Salary Expense         NGN 5,000,000
    CR PAYE Payable                       NGN   500,000
    CR Pension Payable                    NGN   400,000
    CR NHF Payable                        NGN   125,000
    CR Net Salary Payable                 NGN 3,975,000
```

---

### 3.3 Leave Management

**Goal**: Request, approve, and track employee leave.

**Journey Flow**:

1. **Configure Leave Types**
   - Page: `/hr/leave`
   - API: `GET/POST /api/hr/leave/types`
   - Types: Annual, Sick, Maternity, Paternity, etc.

2. **Leave Request**
   - API: `POST /api/hr/leave/applications`
   - Fields: Type, start date, end date, reason

3. **Approval Workflow**
   - API: `POST /api/hr/leave/applications/{id}/approve`
   - Manager approval required

4. **Leave Balance Update**
   - Automatic deduction from entitlement
   - Accrual tracking

5. **Attendance Integration**
   - Page: `/hr/attendance`
   - Leave days marked automatically

---

### 3.4 Attendance Tracking

**Goal**: Record and monitor employee attendance.

**Steps**:

1. **Clock In/Out**
   - Page: `/hr/attendance`
   - API: `POST /api/hr/attendance/clock`
   - Methods: Web, mobile, biometric integration

2. **Shift Management**
   - API: `GET/POST /api/hr/shifts`
   - Define work schedules

3. **Attendance Reports**
   - API: `GET /api/hr/attendance/report`
   - Late arrivals, absences, overtime

4. **Payroll Integration**
   - Attendance affects payroll calculation
   - Overtime pay, deductions for absence

---

## 4. Expense Management Journeys

### 4.1 Expense Claim Workflow

**Goal**: Submit, approve, and reimburse employee expenses.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Create Claim   │ -> │   Approval      │ -> │  Reimbursement  │
│                 │    │                 │    │                 │
│ /expenses/      │    │ /expenses/      │    │ /expenses/      │
│ claims/new      │    │ approvals       │    │ claims/[id]     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Create Expense Claim**
   - Page: `/expenses/claims/new`
   - API: `POST /api/expenses/claims`
   - Fields: Date, category, amount, description
   - Upload receipt image

2. **Policy Validation**
   - Service: `expense_policy_service.py`
   - Checks: Spending limits, valid categories, receipt required

3. **Approval Queue**
   - Page: `/expenses/approvals`
   - API: `GET /api/expenses/claims?status=pending`
   - Manager reviews and approves/rejects

4. **Bulk Approval**
   - API: `POST /api/expenses/claims/bulk-approve`
   - Select multiple claims

5. **Rejection with Reason**
   - API: `POST /api/expenses/claims/{id}/reject`
   - Reason required, employee notified

6. **Reimbursement**
   - API: `POST /api/expenses/claims/{id}/reimburse`
   - Creates AP payment or payroll deduction

7. **GL Posting**
   - Service: `expense_posting_service.py`
   - Creates expense entries

---

### 4.2 Cash Advance Workflow

**Goal**: Request and settle cash advances.

**Journey Flow**:

1. **Request Advance**
   - Page: `/expenses/advances/new`
   - API: `POST /api/expenses/advances`
   - Fields: Amount, purpose, expected settlement date

2. **Approval**
   - API: `POST /api/expenses/advances/{id}/approve`

3. **Disbursement**
   - Record payment to employee
   - Advance balance tracked

4. **Settlement**
   - Submit expense claims against advance
   - API: `POST /api/expenses/advances/{id}/settle`
   - Return unused balance

---

### 4.3 Corporate Card Management

**Goal**: Manage corporate cards and reconcile transactions.

**Journey Flow**:

1. **Card Setup**
   - Page: `/expenses/cards/new`
   - API: `POST /api/expenses/cards`
   - Assign to employee

2. **Statement Import**
   - Page: `/expenses/statements/import`
   - API: `POST /api/expenses/statements/import`
   - Formats: CSV, OFX

3. **Transaction Categorization**
   - Page: `/expenses/transactions`
   - API: `PATCH /api/expenses/transactions/{id}`
   - Assign category, cost center

4. **Exclusion/Personal Marking**
   - API: `POST /api/expenses/transactions/{id}/exclude`
   - Mark non-business transactions

5. **Reconciliation**
   - Page: `/expenses/statements`
   - Match statement balance

---

## 5. Support & Helpdesk Journeys

### 5.1 Ticket Lifecycle

**Goal**: Handle customer support request from creation to resolution.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Ticket Created │ -> │   Assignment    │ -> │   Resolution    │
│                 │    │                 │    │                 │
│ /support/       │    │ /support/       │    │ /support/       │
│ tickets/new     │    │ routing         │    │ tickets/[id]    │
│ or Inbox        │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Complete     │ <- │   CSAT Survey   │ <- │    Closure      │
│                 │    │                 │    │                 │
│ Analytics       │    │ /support/csat   │    │ Ticket Resolved │
│ Updated         │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Ticket Creation**
   - Page: `/support/tickets/new`
   - API: `POST /api/support/tickets`
   - Sources: Manual, email, inbox conversation
   - Fields: Subject, description, contact, priority

2. **Auto-Routing**
   - Service: `routing_engine.py`
   - Page: `/support/routing`
   - Rules: Category, priority, workload balancing
   - Assigns to agent/team

3. **SLA Tracking**
   - Service: `sla_engine.py`
   - Page: `/support/sla`
   - Tracks: First response time, resolution time
   - Breach alerts

4. **Agent Work**
   - Page: `/support/tickets/[id]`
   - API: `GET /api/support/tickets/{id}`
   - Add notes, update status, escalate

5. **Resolution**
   - API: `PATCH /api/support/tickets/{id}`
   - Status: Open → In Progress → Resolved

6. **CSAT Survey**
   - Page: `/support/csat`
   - API: `POST /api/support/csat/send`
   - Triggered on ticket closure

7. **Analytics**
   - Page: `/support/analytics`
   - API: `GET /api/support/analytics`
   - Metrics: Resolution time, volume, satisfaction

---

### 5.2 SLA Management

**Goal**: Configure and monitor Service Level Agreements.

**Steps**:

1. **Create SLA Policy**
   - Page: `/support/sla`
   - API: `POST /api/support/sla/policies`
   - Define response/resolution times by priority

2. **Business Hours Calendar**
   - API: `POST /api/support/sla/calendars`
   - Exclude holidays, set working hours

3. **Breach Monitoring**
   - Service: `sla_engine.py`
   - Automatic notifications before breach

4. **Escalation Rules**
   - API: `POST /api/support/sla/escalations`
   - Auto-escalate approaching breaches

---

### 5.3 Support Automation

**Goal**: Automate common support workflows.

**Steps**:

1. **Create Automation Rule**
   - Page: `/support/automation`
   - API: `POST /api/support/automation/rules`
   - Triggers: New ticket, status change, time-based

2. **Define Actions**
   - Assign to agent
   - Change priority
   - Send notification
   - Add tags

3. **Monitor Execution**
   - Page: `/support/automation`
   - View automation logs

---

## 6. Inbox & Communication Journeys

### 6.1 Omnichannel Inbox

**Goal**: Manage unified customer conversations across channels.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Incoming       │ -> │   Assignment    │ -> │   Conversation  │
│  Message        │    │                 │    │                 │
│ Email/Chat/     │    │ /inbox/routing  │    │ /inbox          │
│ WhatsApp        │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      v
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Create Ticket  │ <- │   Resolution    │
                       │  (if needed)    │    │                 │
                       │ /support/       │    │ Mark Resolved   │
                       │ tickets/new     │    │                 │
                       └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Message Receipt**
   - Channels: Email, Live Chat, WhatsApp
   - API: Inbound webhooks
   - Creates conversation thread

2. **Auto-Assignment**
   - Page: `/inbox/routing`
   - Service: `routing_engine.py`
   - Rules-based or round-robin

3. **Agent Response**
   - Page: `/inbox`
   - API: `POST /api/inbox/conversations/{id}/messages`
   - Canned responses available

4. **Ticket Creation**
   - From conversation: "Create Ticket"
   - API: `POST /api/support/tickets`
   - Links to conversation

5. **Resolution**
   - API: `PATCH /api/inbox/conversations/{id}`
   - Status: Open → Resolved

---

### 6.2 Channel Configuration

**Goal**: Set up communication channels.

**Steps**:

1. **Email Channel**
   - Page: `/inbox/channels/email`
   - Configure SMTP/IMAP

2. **Live Chat Widget**
   - Page: `/inbox/channels/chat`
   - Embed code for website

3. **WhatsApp Business**
   - Page: `/inbox/channels/whatsapp`
   - API integration setup

---

## 7. Inventory & Stock Journeys

### 7.1 Stock Receipt

**Goal**: Receive goods into warehouse.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Purchase Order │ -> │ Purchase Receipt│ -> │  Stock Updated  │
│                 │    │                 │    │                 │
│ /purchasing/    │    │ /inventory/     │    │ /inventory/     │
│ orders          │    │ purchase-       │    │ stock-ledger    │
│                 │    │ receipts        │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Create Purchase Order**
   - Page: `/purchasing/orders/new`
   - API: `POST /api/purchasing/orders`

2. **Receive Goods**
   - Page: `/inventory/purchase-receipts`
   - API: `POST /api/inventory/stock-entries`
   - Type: Material Receipt
   - Links to PO

3. **Batch/Serial Recording**
   - For tracked items
   - API: `POST /api/inventory/batches` or `/serials`

4. **Stock Ledger Update**
   - Page: `/inventory/stock-ledger`
   - Valuation method: FIFO or Average

5. **Landed Cost Allocation**
   - Page: `/inventory/landed-cost-vouchers`
   - API: `POST /api/inventory/landed-cost`
   - Adds freight, customs to item cost

---

### 7.2 Warehouse Transfer

**Goal**: Move stock between warehouses.

**Steps**:

1. **Create Transfer Request**
   - Page: `/inventory/transfers/new`
   - API: `POST /api/inventory/transfers`
   - Source warehouse, destination, items

2. **Approval** (if required)
   - API: `POST /api/inventory/transfers/{id}/approve`

3. **Issue from Source**
   - Stock entry: Material Transfer (Out)

4. **Receipt at Destination**
   - Stock entry: Material Transfer (In)

5. **Transit Tracking**
   - Status: Pending → In Transit → Received

---

### 7.3 Stock Valuation

**Goal**: Calculate inventory value for financial reporting.

**Steps**:

1. **View Valuation**
   - Page: `/inventory/valuation`
   - API: `GET /api/inventory/valuation`
   - Methods: FIFO, Weighted Average

2. **Item Detail**
   - Page: `/inventory/valuation/[item_code]`
   - Shows in/out transactions and running value

3. **Reorder Alerts**
   - Page: `/inventory/reorder`
   - Items below reorder point

---

## 8. Purchasing & AP Journeys

### 8.1 Procure to Pay

**Goal**: Complete purchasing cycle from request to payment.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Purchase Order  │ -> │   Goods Receipt │ -> │  Supplier Bill  │
│                 │    │                 │    │                 │
│ /purchasing/    │    │ /inventory/     │    │ /purchasing/    │
│ orders/new      │    │ purchase-       │    │ bills           │
│                 │    │ receipts        │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Complete     │ <- │   Allocation    │ <- │    Payment      │
│                 │    │                 │    │                 │
│ Supplier Paid   │    │ Allocate to     │    │ /purchasing/    │
│                 │    │ bill            │    │ payments/new    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Create Purchase Order**
   - Page: `/purchasing/orders/new`
   - API: `POST /api/purchasing/orders`
   - Fields: Supplier, items, terms

2. **PO Approval**
   - API: `POST /api/purchasing/orders/{id}/approve`

3. **Goods Receipt**
   - Page: `/inventory/purchase-receipts`
   - API: `POST /api/inventory/stock-entries`

4. **Supplier Invoice (Bill)**
   - Page: `/purchasing/bills`
   - API: `POST /api/accounting/bills`
   - Match to PO and GRN (3-way match)

5. **Bill Posting**
   - API: `POST /api/accounting/bills/{id}/post`
   - Creates AP liability

6. **Payment Processing**
   - Page: `/purchasing/payments/new`
   - API: `POST /api/accounting/payments/outgoing`

7. **Payment Allocation**
   - API: `POST /api/accounting/allocations`
   - Links payment to bill(s)

**GL Impact**:
```
Bill Posting:
  DR Inventory/Expense     NGN 100,000
  DR VAT Receivable        NGN   7,500
    CR Accounts Payable                NGN 100,000
    CR WHT Payable                     NGN   7,500

Payment:
  DR Accounts Payable      NGN 100,000
    CR Bank Account                    NGN 100,000
```

---

### 8.2 AP Aging Analysis

**Goal**: Monitor outstanding payables.

**Steps**:

1. **View Aging Report**
   - Page: `/purchasing/aging`
   - API: `GET /api/accounting/payables/aging`
   - Buckets: Current, 30, 60, 90, 90+ days

2. **Supplier Drill-down**
   - Page: `/purchasing/suppliers/[id]`
   - View all outstanding bills

3. **Payment Scheduling**
   - Plan payments based on due dates
   - Cash flow management

---

## 9. Field Service Journeys

### 9.1 Service Order Dispatch

**Goal**: Schedule and complete field service work.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Service Order  │ -> │   Scheduling    │ -> │  Field Work     │
│                 │    │                 │    │                 │
│ /field-service/ │    │ /field-service/ │    │ Mobile App      │
│ orders/new      │    │ schedule        │    │ Check-in/out    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      v
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Invoicing     │ <- │   Completion    │
                       │                 │    │                 │
                       │ /sales/invoices │    │ Photos,         │
                       │                 │    │ Checklist       │
                       └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Create Service Order**
   - Page: `/field-service/orders/new`
   - API: `POST /api/field-service/orders`
   - Fields: Customer, service type, location, urgency

2. **Assign Technician**
   - Page: `/field-service/schedule`
   - API: `PATCH /api/field-service/orders/{id}/assign`
   - Consider: Skills, availability, proximity

3. **Dispatch**
   - Notification to technician
   - Service: `customer_notifications.py`
   - Customer SMS with ETA

4. **Field Execution**
   - Technician check-in
   - Complete checklist
   - Upload photos

5. **Completion**
   - API: `POST /api/field-service/orders/{id}/complete`
   - Customer signature (if required)

6. **Invoicing**
   - Generate invoice from service order
   - Parts + labor billing

---

## 10. Performance Management Journeys

### 10.1 Performance Review Cycle

**Goal**: Conduct employee performance reviews.

**Journey Flow**:

1. **Create Review Period**
   - Page: `/performance/periods`
   - API: `POST /api/performance/periods`
   - Annual, quarterly cycles

2. **Define Review Templates**
   - Page: `/performance/templates`
   - API: `POST /api/performance/templates`
   - Competencies, rating scales

3. **Initiate Reviews**
   - API: `POST /api/performance/reviews/batch-create`
   - Assign to managers

4. **Self-Assessment**
   - Employee completes their portion

5. **Manager Assessment**
   - Page: `/performance/reviews`
   - API: `PATCH /api/performance/reviews/{id}`

6. **Calibration** (optional)
   - Normalize scores across teams

7. **Finalization**
   - API: `POST /api/performance/reviews/{id}/finalize`
   - Employee acknowledgment

8. **Notifications**
   - Service: `performance_notification_service.py`

---

### 10.2 KPI Tracking

**Goal**: Monitor key performance indicators.

**Steps**:

1. **Define KPIs**
   - Page: `/performance/kpis`
   - API: `POST /api/performance/kpis`
   - Targets, measurement methods

2. **Record Actuals**
   - API: `POST /api/performance/kpis/{id}/actuals`
   - Manual or automated data collection

3. **Scorecard View**
   - Page: `/performance/scorecards`
   - Visual dashboard of KPI status

---

## 11. Admin & Settings Journeys

### 11.1 User & Role Management

**Goal**: Manage system users and permissions.

**Steps**:

1. **Create Role**
   - Page: `/admin/roles`
   - API: `POST /api/admin/roles`
   - Define scope permissions

2. **Assign Users to Roles**
   - API: `POST /api/admin/roles/{id}/users`

3. **Create Service Token**
   - For API integrations
   - API: `POST /api/admin/service-tokens`

4. **Revoke Access**
   - API: `DELETE /api/admin/tokens/{id}`

---

### 11.2 Webhook Configuration

**Goal**: Set up inbound and outbound webhooks.

**Inbound Webhooks** (receive from external services):

1. **View Provider Webhooks**
   - Page: `/admin/webhooks/inbound`
   - API: `GET /api/admin/webhooks/inbound`

2. **Copy Webhook URL**
   - Unique URL per provider (Paystack, Flutterwave, etc.)

3. **Rotate Secret**
   - API: `POST /api/admin/webhooks/inbound/{provider}/rotate`

4. **View Delivery Logs**
   - API: `GET /api/admin/webhooks/logs`

**Outbound Webhooks** (send to external services):

1. **Create Webhook**
   - Page: `/admin/webhooks/omni`
   - API: `POST /api/admin/webhooks/omni`
   - Fields: URL, events, secret

2. **Test Webhook**
   - API: `POST /api/admin/webhooks/omni/{id}/test`

3. **Retry Failed Deliveries**
   - API: `POST /api/admin/webhooks/logs/{id}/retry`

---

### 11.3 System Settings

**Goal**: Configure global application settings.

**Categories**:

| Setting | Page | Purpose |
|---------|------|---------|
| Company Info | `/admin/settings/company` | Legal name, address, logo |
| Email/SMTP | `/admin/settings/email` | Outbound email configuration |
| SMS Providers | `/admin/settings/sms` | Termii, Africa's Talking |
| Payment Gateways | `/admin/settings/payments` | Paystack, Flutterwave keys |
| Notifications | `/admin/settings/notifications` | System alert preferences |
| Branding | `/admin/settings/branding` | Logos, colors |
| Localization | `/admin/settings/localization` | Timezone, date format |

---

## 12. Integration & Sync Journeys

### 12.1 Data Synchronization

**Goal**: Sync data from external systems.

**Sources**:
- **Splynx**: ISP billing (customers, invoices, payments)
- **ERPNext**: ERP data (inventory, accounting)
- **Chatwoot**: Support conversations

**Journey Flow**:

1. **Configure Connection**
   - Environment variables or settings
   - API keys, endpoints

2. **Initial Sync**
   - API: `POST /api/sync/all`
   - Full data import

3. **Incremental Sync**
   - Celery beat: Every 15 minutes
   - Only changed records

4. **Monitor Status**
   - Page: `/sync`
   - API: `GET /api/sync/status`

5. **View Logs**
   - API: `GET /api/sync/logs`
   - Error tracking

---

### 12.2 Data Import

**Goal**: Bulk import data from files.

**Steps**:

1. **Download Template**
   - API: `GET /api/imports/template/{entity}`
   - Excel/CSV format

2. **Upload File**
   - API: `POST /api/imports/upload`

3. **Validation Preview**
   - API: `POST /api/imports/validate`
   - Shows errors before import

4. **Execute Import**
   - API: `POST /api/imports/execute`

5. **Review Results**
   - Success/failure counts
   - Error details

---

## Appendix: API Endpoint Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/token` | POST | Get JWT token |
| `/api/auth/refresh` | POST | Refresh token |
| `/api/auth/revoke` | POST | Revoke token |

### Core Entities

| Module | Base Endpoint |
|--------|---------------|
| Contacts | `/api/contacts` |
| Customers | `/api/customers` |
| Invoices | `/api/accounting/invoices` |
| Payments | `/api/accounting/payments` |
| Bills | `/api/accounting/bills` |
| Employees | `/api/hr/employees` |
| Tickets | `/api/support/tickets` |
| Inventory | `/api/inventory` |

### Reporting

| Report | Endpoint |
|--------|----------|
| Balance Sheet | `/api/accounting/balance-sheet` |
| Income Statement | `/api/accounting/income-statement` |
| Trial Balance | `/api/accounting/trial-balance` |
| AR Aging | `/api/accounting/receivables/aging` |
| AP Aging | `/api/accounting/payables/aging` |

---

## Appendix: E2E Test Coverage

The following user journeys are covered by automated E2E tests:

| Module | Test File | Scenarios |
|--------|-----------|-----------|
| Banking | `banking.spec.ts` | 22 tests |
| Payroll | `payroll.spec.ts` | 19 tests |
| Expenses | `expenses.spec.ts` | 18 tests |
| Contacts | `contacts.spec.ts` | 13 tests |
| Support | `support-tickets.spec.ts` | 15 tests |
| Settings | `settings.spec.ts` | 17 tests |
| Webhooks | `webhooks.spec.ts` | 17 tests |

**Total E2E Tests**: 121 scenarios

---

*Document generated: 2025-12-19*
*Version: 1.0*
