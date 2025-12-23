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
14. [Analytics Journeys](#13-analytics-journeys)
15. [Assets Journeys](#14-assets-journeys)
16. [Banking Journeys](#15-banking-journeys)
17. [CRM Journeys](#16-crm-journeys)
18. [Customer Explorer Journeys](#17-customer-explorer-journeys)
19. [Fleet Management Journeys](#18-fleet-management-journeys)
20. [Projects Journeys](#19-projects-journeys)
21. [Reports Journeys](#20-reports-journeys)
22. [Data Insights Journeys](#21-data-insights-journeys)

---

## Overview

This document describes end-to-end user journeys in the Dotmac Business Operating System (BOS). Each journey represents a complete workflow from initiation to completion, including:
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
| Sales Rep | `crm:read`, `crm:write`, `sales:read`, `sales:write` | CRM & sales |
| Support Agent | `customers:read`, `tickets:*` | Helpdesk access |
| Read-Only | `analytics:read`, `explore:read` | Dashboard viewing |

---

## 1. Sales & CRM Journeys

### 1.1 Lead to Customer Conversion

**Goal**: Convert a potential lead into a paying customer through the sales funnel.

**Entry Points**:
- Manual lead creation via `/crm/contacts/new`
- Lead capture from website forms (via webhook)
- Import from external CRM via `/crm/tools/import`
- Inbox conversation conversion

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Lead Capture   │ -> │  Qualification  │ -> │   Opportunity   │
│                 │    │                 │    │                 │
│ /crm/contacts/  │    │ /crm/lifecycle/ │    │ /crm/pipeline/  │
│ leads           │    │ qualification   │    │ opportunities   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Customer     │ <- │   Quotation     │ <- │     Deal        │
│                 │    │                 │    │   Negotiation   │
│ /crm/contacts/  │    │ /sales/         │    │ /crm/pipeline   │
│ customers       │    │ quotations      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Lead Capture**
   - Page: `/crm/contacts/new`
   - API: `POST /api/contacts`
   - Fields: Name, email, phone, source, company, contact_type=lead
   - Triggers: Lead scoring automation

2. **Lead Qualification**
   - Page: `/crm/contacts/[id]`
   - API: `PATCH /api/contacts/{id}`
   - Actions: Update status, add notes, schedule follow-up
   - Scoring: Automatic lead score calculation

3. **Opportunity Creation**
   - Page: `/crm/pipeline/opportunities/new`
   - API: `POST /api/crm/opportunities`
   - Fields: Deal value, expected close date, probability
   - Links to contact record

4. **Pipeline Management**
   - Page: `/crm/pipeline`
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

### 1.4 Additional Sales Pages

The Sales module handles financial transactions. CRM-related pages (contacts, leads, pipeline, activities) are now in the `/crm` module.

**Quotations**:
- `/sales/quotations` - Quotation list
- `/sales/quotations/new` - Create quotation
- `/sales/quotations/[id]` - Quotation details
- `/sales/quotations/[id]/edit` - Edit quotation

**Sales Orders**:
- `/sales/orders` - Sales order list
- `/sales/orders/new` - Create sales order
- `/sales/orders/[id]` - Order details
- `/sales/orders/[id]/edit` - Edit order

**Invoices**:
- `/sales/invoices` - Invoice list
- `/sales/invoices/new` - Create invoice
- `/sales/invoices/[id]` - Invoice details
- `/sales/invoices/[id]/edit` - Edit invoice

**Payments**:
- `/sales/payments` - Payment list
- `/sales/payments/new` - Record payment
- `/sales/payments/[id]` - Payment details
- `/sales/payments/[id]/edit` - Edit payment

**Credit Notes**:
- `/sales/credit-notes` - Credit note list
- `/sales/credit-notes/new` - Create credit note
- `/sales/credit-notes/[id]` - Credit note details
- `/sales/credit-notes/[id]/edit` - Edit credit note

**Analytics**:
- `/sales/analytics` - Revenue analytics dashboard

**Settings**:
- `/sales/settings/customer-groups` - Customer group configuration
- `/sales/settings/sales-persons` - Sales person management
- `/sales/settings/territories` - Territory hierarchy

**Note**: Customer and lead management is now in the CRM module at `/crm/contacts/*`. Pipeline and activities are at `/crm/pipeline` and `/crm/activities`.

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

### 2.6 Additional Finance Pages

The Finance & Accounting module includes these additional pages:

**Financial Statements**:
- `/books/balance-sheet` - Balance sheet report
- `/books/income-statement` - Income statement (P&L)
- `/books/cash-flow` - Cash flow statement
- `/books/equity-statement` - Statement of changes in equity
- `/books/trial-balance` - Trial balance report
- `/books/general-ledger` - General ledger entries

**Banking**:
- `/books/bank-accounts` - Bank account list
- `/books/bank-transactions` - Bank transaction list
- `/books/bank-transactions/new` - Create bank transaction
- `/books/bank-transactions/import` - Import bank statements
- `/books/bank-transactions/[id]` - Transaction details

**Accounts Payable (AP)**:
- `/books/accounts-payable` - AP dashboard
- `/books/accounts-payable/bills` - Bill list
- `/books/accounts-payable/bills/new` - Create bill
- `/books/accounts-payable/payments` - AP payments
- `/books/accounts-payable/suppliers` - Supplier list
- `/books/accounts-payable/debit-notes` - Debit notes
- `/books/accounts-payable/debit-notes/new` - Create debit note

**Accounts Receivable (AR)**:
- `/books/accounts-receivable` - AR dashboard
- `/books/accounts-receivable/invoices` - Invoice list
- `/books/accounts-receivable/invoices/new` - Create invoice
- `/books/accounts-receivable/payments` - AR payments
- `/books/accounts-receivable/payments/new` - Record payment
- `/books/accounts-receivable/customers` - Customer list
- `/books/accounts-receivable/credit-notes` - Credit notes
- `/books/accounts-receivable/credit-notes/new` - Create credit note
- `/books/accounts-receivable/credit` - Credit management
- `/books/accounts-receivable/dunning` - Dunning management

**Tax Management**:
- `/books/tax` - Tax dashboard
- `/books/tax/vat` - VAT management
- `/books/tax/wht` - Withholding tax
- `/books/tax/paye` - PAYE tax
- `/books/tax/cit` - Corporate income tax
- `/books/tax/filing` - Tax filing
- `/books/tax/einvoice` - E-invoicing
- `/books/tax/settings` - Tax settings

**Other**:
- `/books/gl-expenses` - GL expense entries
- `/books/controls` - Financial controls
- `/books/purchase-invoices` - Purchase invoice list
- `/books/purchase-invoices/[id]` - Purchase invoice details
- `/books/suppliers` - Supplier management
- `/books/suppliers/new` - Create supplier
- `/books/suppliers/[id]` - Supplier details

**Settings**:
- `/books/settings` - Books settings dashboard
- `/books/settings/cost-centers` - Cost center configuration
- `/books/settings/fiscal-years` - Fiscal year management
- `/books/settings/modes-of-payment` - Payment modes

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

### 3.4 Additional HR Pages

The HR module includes these additional pages:

**Master Data**:
- `/hr/masters/employees` - Employee list with inline CRUD
- `/hr/masters/departments` - Department management with inline CRUD
- `/hr/masters/designations` - Designation management with inline CRUD

**Core HR Pages**:
- `/hr` - HR dashboard
- `/hr/recruitment` - Recruitment management
- `/hr/payroll` - Payroll dashboard
- `/hr/payroll/settings` - Payroll configuration (salary components, structures, deduction rules, regions)
- `/hr/payroll/run` - Payroll run wizard (step-by-step payroll processing)
- `/hr/payroll/payslips` - Salary slips list with filters
- `/hr/payroll/payslips/[id]` - Salary slip detail view
- `/hr/leave` - Leave management
- `/hr/attendance` - Attendance tracking
- `/hr/lifecycle` - Employee lifecycle events
- `/hr/appraisals` - Performance appraisals
- `/hr/training` - Training management

**Analytics & Settings**:
- `/hr/analytics` - HR analytics dashboard
- `/hr/settings` - HR module settings

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

### 4.3 Additional Expense Pages

The Expense Management module includes these additional pages:

**Core Pages**:
- `/expenses` - Expense dashboard
- `/expenses/claims` - Expense claims list
- `/expenses/claims/new` - Create expense claim
- `/expenses/claims/[id]` - Claim details
- `/expenses/advances` - Cash advances list
- `/expenses/advances/new` - Request cash advance
- `/expenses/advances/[id]` - Advance details
- `/expenses/approvals` - Pending approvals
- `/expenses/transactions` - Transaction list

**Corporate Cards**:
- `/expenses/cards` - Card list
- `/expenses/cards/[id]` - Card details
- `/expenses/card-analytics` - Card usage analytics
- `/expenses/statements` - Statement list
- `/expenses/statements/import` - Import statements

**Reports & Settings**:
- `/expenses/reports` - Expense reports
- `/expenses/settings` - Expense module settings

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

### 5.3 Additional Support Pages

The Support & Helpdesk module includes these additional pages:

**Core Pages**:
- `/support` - Support dashboard
- `/support/tickets` - Ticket list
- `/support/tickets/new` - Create ticket
- `/support/tickets/[id]` - Ticket details
- `/support/routing` - Ticket routing rules

**Team Management**:
- `/support/agents` - Agent list and management
- `/support/teams` - Support team management

**Configuration**:
- `/support/sla` - SLA configuration
- `/support/automation` - Automation rules
- `/support/canned-responses` - Canned response templates
- `/support/kb` - Knowledge base articles
- `/support/csat` - Customer satisfaction settings

**Analytics & Settings**:
- `/support/analytics` - Support analytics dashboard
- `/support/settings` - Support module settings

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

### 6.3 Additional Inbox Pages

The Inbox & Communication module includes these additional pages:

**Core Inbox**:
- `/inbox` - Unified inbox view
- `/inbox/unassigned` - Unassigned conversations
- `/inbox/routing` - Conversation routing rules
- `/inbox/routing/teams` - Team routing configuration

**Channels**:
- `/inbox/channels` - Channel overview
- `/inbox/channels/email` - Email channel settings
- `/inbox/channels/chat` - Live chat settings
- `/inbox/channels/whatsapp` - WhatsApp integration

**Contacts**:
- `/inbox/contacts` - Contact list
- `/inbox/contacts/companies` - Company contacts

**Analytics**:
- `/inbox/analytics` - Inbox analytics overview
- `/inbox/analytics/agents` - Agent performance
- `/inbox/analytics/channels` - Channel metrics

**Settings**:
- `/inbox/settings` - Inbox settings
- `/inbox/settings/canned` - Canned responses
- `/inbox/settings/signatures` - Email signatures

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

### 7.4 Additional Inventory Pages

The Inventory & Stock module includes these additional pages:

**Item Management**:
- `/inventory` - Inventory dashboard
- `/inventory/items` - Item list
- `/inventory/items/new` - Create item
- `/inventory/items/[id]` - Item details

**Stock Movements**:
- `/inventory/stock-entries` - Stock entry list
- `/inventory/stock-entries/new` - Create stock entry
- `/inventory/stock-entries/[id]` - Stock entry details (Material Receipt/Issue/Transfer)

**Tracking**:
- `/inventory/batches` - Batch tracking
- `/inventory/serials` - Serial number tracking
- `/inventory/transfers` - Stock transfer requests
- `/inventory/transfers/new` - Create transfer
- `/inventory/transfers/[id]` - Transfer details

**Warehouses**:
- `/inventory/warehouses` - Warehouse list
- `/inventory/warehouses/new` - Create warehouse

**Reports & Settings**:
- `/inventory/landed-cost-vouchers` - Landed cost vouchers
- `/inventory/landed-cost-vouchers/[id]` - Voucher details
- `/inventory/settings/item-groups` - Item group configuration

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

### 8.3 Additional Purchasing Pages

The Purchasing & AP module includes these additional pages:

**Purchase Orders**:
- `/purchasing` - Purchasing dashboard
- `/purchasing/orders` - Purchase order list
- `/purchasing/orders/new` - Create purchase order
- `/purchasing/orders/[id]` - Order details

**Suppliers**:
- `/purchasing/suppliers` - Supplier list
- `/purchasing/suppliers/new` - Create supplier
- `/purchasing/suppliers/[id]` - Supplier details

**Bills & Payments**:
- `/purchasing/bills` - Bill list
- `/purchasing/bills/[id]` - Bill details
- `/purchasing/payments` - Payment list
- `/purchasing/payments/[id]` - Payment details
- `/purchasing/debit-notes` - Debit note list
- `/purchasing/debit-notes/[id]` - Debit note details

**Expenses**:
- `/purchasing/expenses` - Expense list
- `/purchasing/erpnext-expenses` - ERPNext synced expenses
- `/purchasing/erpnext-expenses/[id]` - Expense details

**Reports**:
- `/purchasing/aging` - AP aging report
- `/purchasing/analytics` - Purchasing analytics

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

### 9.2 Additional Field Service Pages

The Field Service module includes these additional pages:

**Service Orders**:
- `/field-service` - Field service dashboard
- `/field-service/orders` - Service order list
- `/field-service/orders/new` - Create service order
- `/field-service/orders/[id]` - Order details
- `/field-service/schedule` - Scheduling calendar

**Teams & Analytics**:
- `/field-service/teams` - Field service team management
- `/field-service/analytics` - Field service analytics

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

### 10.3 Additional Performance Pages

The Performance Management module includes these additional pages:

**Core Pages**:
- `/performance/periods` - Evaluation period management
- `/performance/templates` - Review template management
- `/performance/reviews` - Performance review list
- `/performance/kpis` - KPI management
- `/performance/scorecards` - Scorecard dashboard

**KRAs**:
- `/performance/kras` - Key Result Area management

**Reports & Analytics**:
- `/performance/analytics` - Performance analytics
- `/performance/reports/bonus` - Bonus calculation reports

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

### 11.4 Additional Admin Pages

The Admin module includes these additional pages:

**Core Admin**:
- `/admin/roles` - Role management
- `/admin/platform` - Platform administration
- `/admin/security` - Security settings

**Webhooks**:
- `/admin/webhooks` - Webhook overview
- `/admin/webhooks/[id]` - Webhook details
- `/admin/webhooks/inbound` - Inbound webhook providers
- `/admin/webhooks/inbound/events` - Inbound event log
- `/admin/webhooks/inbound/events/[id]` - Event details
- `/admin/webhooks/inbound/providers/[name]` - Provider config
- `/admin/webhooks/omni` - Outbound webhooks
- `/admin/webhooks/omni/[id]` - Outbound webhook details

**Settings**:
- `/admin/settings/[group]` - Dynamic settings by group
- `/admin/settings/audit` - Audit log

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

## 13. Analytics Journeys

### 13.1 Business Intelligence Dashboard

**Goal**: Monitor key business metrics across revenue, sales, support, collections, and operations.

**Entry Point**: `/analytics`

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Dashboard      │ -> │    Tab          │ -> │    Drill-down   │
│  Overview       │    │  Selection      │    │    Analysis     │
│                 │    │                 │    │                 │
│ /analytics      │    │ Revenue/Sales/  │    │ Detailed        │
│                 │    │ Support/Ops     │    │ Metrics         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **View Key Metrics**
   - Page: `/analytics`
   - API: `GET /api/analytics/overview`
   - Metrics: DSO, SLA attainment, pipeline conversion, outstanding amounts

2. **Revenue Analysis**
   - API: `GET /api/analytics/revenue-trend`
   - API: `GET /api/analytics/dso-trend`
   - API: `GET /api/analytics/revenue-by-territory`
   - Charts: Revenue trend, DSO, churn

3. **Sales Pipeline Analysis**
   - API: `GET /api/analytics/pipeline`
   - API: `GET /api/analytics/quotation-trend`
   - Funnel visualization, conversion rates

4. **Support/SLA Analysis**
   - API: `GET /api/analytics/sla-attainment`
   - API: `GET /api/analytics/agent-productivity`
   - API: `GET /api/analytics/tickets-by-type`
   - SLA gauge, agent performance charts

5. **Collections Analysis**
   - API: `GET /api/analytics/invoice-aging`
   - API: `GET /api/analytics/aging-by-segment`
   - Aging breakdown by bucket and segment

6. **Operations Analysis**
   - API: `GET /api/analytics/network-device-status`
   - API: `GET /api/analytics/ip-utilization`
   - API: `GET /api/analytics/expenses-by-category`
   - Network health, IP utilization, expense trends

**Filters**:
- Time range: 6M, 12M, 24M
- Date range picker
- Tab-based navigation

---

## 14. Assets Journeys

### 14.1 Fixed Asset Management

**Goal**: Track, depreciate, and maintain company fixed assets.

**Entry Point**: `/assets`

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Asset          │ -> │  Depreciation   │ -> │  Maintenance    │
│  Registration   │    │  Tracking       │    │  & Disposal     │
│                 │    │                 │    │                 │
│ /assets/list    │    │ /assets/        │    │ /assets/        │
│                 │    │ depreciation    │    │ maintenance     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **View Asset Dashboard**
   - Page: `/assets`
   - API: `GET /api/assets/summary`
   - Shows: Total assets, book value, accumulated depreciation

2. **Asset Registration**
   - Page: `/assets/list`
   - API: `POST /api/assets`
   - Fields: Name, category, purchase date, value, location

3. **Asset Categories**
   - Page: `/assets/categories`
   - API: `GET/POST /api/assets/categories`
   - Configure depreciation methods per category

4. **Depreciation Processing**
   - Page: `/assets/depreciation`
   - API: `GET /api/assets/depreciation/pending`
   - API: `POST /api/assets/depreciation/run`
   - Methods: Straight-line, declining balance

5. **Pending Depreciation**
   - Page: `/assets/depreciation/pending`
   - API: `GET /api/assets/depreciation/pending`
   - Review and post depreciation entries

6. **Maintenance Tracking**
   - Page: `/assets/maintenance`
   - API: `GET /api/assets/maintenance-due`
   - Schedule and track maintenance

7. **Warranty Tracking**
   - Page: `/assets/maintenance/warranty`
   - API: `GET /api/assets/warranty-expiring`
   - Monitor warranty expiration

8. **Insurance Tracking**
   - Page: `/assets/maintenance/insurance`
   - API: `GET /api/assets/insurance-expiring`
   - Track insurance coverage

**GL Impact**:
```
Depreciation Entry:
  DR Depreciation Expense     NGN XX,XXX
    CR Accumulated Depreciation         NGN XX,XXX
```

---

### 14.3 Additional Asset Pages

The Assets module includes these additional pages:

**Core Pages**:
- `/assets` - Assets dashboard
- `/assets/list` - Asset list
- `/assets/list/[id]` - Asset details
- `/assets/categories` - Asset categories
- `/assets/depreciation` - Depreciation overview
- `/assets/depreciation/pending` - Pending depreciation entries

**Maintenance**:
- `/assets/maintenance` - Maintenance dashboard
- `/assets/maintenance/warranty` - Warranty tracking
- `/assets/maintenance/insurance` - Insurance tracking

**Settings**:
- `/assets/settings` - Asset module settings

---

## 15. Banking Journeys

### 15.1 Bank Transaction Management

**Goal**: Import, categorize, and reconcile bank transactions.

**Entry Point**: `/banking` (redirects to `/banking/bank-transactions`)

**Note**: Banking transactions are managed through the Books module. The `/banking` route provides a shortcut that re-exports from `/books/bank-transactions`.

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Import         │ -> │  Categorize     │ -> │  Reconcile      │
│  Statement      │    │  Transactions   │    │                 │
│                 │    │                 │    │                 │
│ /books/bank-    │    │ /books/bank-    │    │ Match to        │
│ transactions/   │    │ transactions    │    │ GL entries      │
│ import          │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **View Bank Accounts**
   - Page: `/banking/bank-accounts` or `/books/bank-accounts`
   - API: `GET /api/banking/accounts`
   - List configured bank accounts

2. **Import Bank Statement**
   - Page: `/books/bank-transactions/import`
   - API: `POST /api/banking/import`
   - Formats: CSV, OFX, QIF

3. **View Transactions**
   - Page: `/banking/bank-transactions` or `/books/bank-transactions`
   - API: `GET /api/banking/transactions`
   - Filter by date, status, account

4. **Transaction Details**
   - Page: `/books/bank-transactions/[id]`
   - API: `GET /api/banking/transactions/{id}`
   - View and update transaction details

5. **Create Manual Transaction**
   - Page: `/books/bank-transactions/new`
   - API: `POST /api/banking/transactions`
   - Manual entry for missing transactions

6. **Categorization**
   - API: `PATCH /api/banking/transactions/{id}`
   - Assign category and GL account

7. **Reconciliation**
   - API: `POST /api/banking/reconcile`
   - Match bank transactions with GL entries
   - Mark as reconciled

---

## 16. CRM Journeys

### 16.1 Unified CRM Module

**Goal**: Manage contacts, leads, pipeline, and customer relationships in a unified CRM system.

**Entry Point**: `/crm`

**Module Structure**:
```
/crm
├── /crm                          # Dashboard (unified metrics)
├── /crm/contacts                 # All contacts directory
│   ├── /crm/contacts/all         # Full directory
│   ├── /crm/contacts/leads       # Leads view
│   ├── /crm/contacts/customers   # Customers view
│   ├── /crm/contacts/organizations
│   ├── /crm/contacts/people
│   ├── /crm/contacts/churned
│   ├── /crm/contacts/[id]        # Contact detail
│   ├── /crm/contacts/[id]/edit
│   └── /crm/contacts/new
├── /crm/pipeline                 # Sales pipeline
│   ├── /crm/pipeline             # Kanban view
│   ├── /crm/pipeline/opportunities
│   └── /crm/pipeline/opportunities/[id]
├── /crm/activities               # Sales activities
├── /crm/lifecycle                # Lead lifecycle
│   ├── /crm/lifecycle/funnel
│   └── /crm/lifecycle/qualification
├── /crm/segments                 # Segmentation
│   ├── /crm/segments/categories
│   ├── /crm/segments/territories
│   ├── /crm/segments/tags
│   └── /crm/segments/lists
├── /crm/tools                    # Bulk operations
│   ├── /crm/tools/import
│   ├── /crm/tools/export
│   ├── /crm/tools/duplicates
│   └── /crm/tools/quality
└── /crm/analytics                # CRM analytics
```

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Contact        │ -> │  Qualification  │ -> │  Customer       │
│  Capture        │    │  & Nurturing    │    │  Conversion     │
│                 │    │                 │    │                 │
│ /crm/contacts/  │    │ /crm/lifecycle/ │    │ Status:         │
│ new             │    │ qualification   │    │ lead->customer  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **View CRM Dashboard**
   - Page: `/crm`
   - API: `GET /api/contacts/dashboard`
   - Shows: Total contacts, leads, prospects, customers, MRR

2. **View Sales Funnel**
   - Page: `/crm/lifecycle/funnel`
   - API: `GET /api/contacts/funnel`
   - Leads created, qualified, converted

3. **Create Contact**
   - Page: `/crm/contacts/new`
   - API: `POST /api/contacts`
   - Fields: Name, email, phone, type, category

4. **List Contacts by Type**
   - Pages: `/crm/contacts/leads`, `/crm/contacts/customers`, `/crm/contacts/people`, `/crm/contacts/organizations`
   - API: `GET /api/contacts?contact_type={type}`

5. **Contact Detail**
   - Page: `/crm/contacts/[id]`
   - API: `GET /api/contacts/{id}`
   - View full contact profile

6. **Edit Contact**
   - Page: `/crm/contacts/[id]/edit`
   - API: `PATCH /api/contacts/{id}`
   - Update contact information

7. **Qualification**
   - Page: `/crm/lifecycle/qualification`
   - API: `PATCH /api/contacts/{id}`
   - Status: unqualified → cold → warm → hot → qualified

8. **Pipeline Management**
   - Page: `/crm/pipeline`
   - API: `GET /api/crm/pipeline`
   - Kanban board for opportunities

9. **Tag Management**
   - Page: `/crm/segments/tags`
   - API: `GET/POST /api/contacts/tags`
   - Organize contacts with tags

10. **Territory Assignment**
    - Page: `/crm/segments/territories`
    - API: `GET/POST /api/contacts/territories`
    - Assign sales territories

11. **Contact Lists**
    - Page: `/crm/segments/lists`
    - API: `GET/POST /api/contacts/lists`
    - Create dynamic contact segments

12. **Data Quality**
    - Page: `/crm/tools/quality`
    - API: `GET /api/contacts/quality`
    - Identify incomplete or duplicate records

13. **Duplicate Detection**
    - Page: `/crm/tools/duplicates`
    - API: `GET /api/contacts/duplicates`
    - Find and merge duplicate contacts

14. **Export/Import**
    - Pages: `/crm/tools/export`, `/crm/tools/import`
    - API: `GET/POST /api/contacts/export`, `POST /api/contacts/import`
    - Bulk data operations

---

### 16.2 CRM Module Pages

The CRM module includes these pages:

**Dashboard**:
- `/crm` - CRM dashboard with unified metrics

**Contacts**:
- `/crm/contacts/all` - All contacts list
- `/crm/contacts/new` - Create contact
- `/crm/contacts/[id]` - Contact details
- `/crm/contacts/[id]/edit` - Edit contact
- `/crm/contacts/leads` - Leads list
- `/crm/contacts/customers` - Customers list
- `/crm/contacts/people` - People list
- `/crm/contacts/organizations` - Organizations list
- `/crm/contacts/churned` - Churned contacts

**Pipeline**:
- `/crm/pipeline` - Pipeline kanban view
- `/crm/pipeline/opportunities` - Opportunities list
- `/crm/pipeline/opportunities/[id]` - Opportunity details
- `/crm/pipeline/opportunities/new` - Create opportunity

**Activities**:
- `/crm/activities` - Sales activities list
- `/crm/activities/new` - Log activity

**Lifecycle**:
- `/crm/lifecycle/funnel` - Sales funnel visualization
- `/crm/lifecycle/qualification` - Lead qualification dashboard

**Segments**:
- `/crm/segments/categories` - Contact categories
- `/crm/segments/territories` - Territory management
- `/crm/segments/tags` - Tag management
- `/crm/segments/lists` - Custom contact lists

**Tools**:
- `/crm/tools/import` - Import contacts
- `/crm/tools/export` - Export contacts
- `/crm/tools/duplicates` - Duplicate detection
- `/crm/tools/quality` - Data quality dashboard

**Analytics**:
- `/crm/analytics` - CRM analytics

**Scopes**: `crm:read`, `crm:write`

**Note**: Old `/contacts/*` paths redirect to `/crm/*` equivalents for backwards compatibility

---

## 17. Customer Explorer Journeys

### 17.1 Customer 360 View

**Goal**: Deep-dive into individual customer data with full 360-degree visibility.

**Entry Point**: `/customers`

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Customer       │ -> │  Customer       │ -> │  360 Analysis   │
│  List           │    │  Selection      │    │                 │
│                 │    │                 │    │                 │
│ /customers      │    │ Click row       │    │ Profile/Finance/│
│                 │    │                 │    │ Services/Network│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **View Customer Dashboard**
   - Page: `/customers`
   - API: `GET /api/customers/dashboard`
   - Metrics: Total customers, active, blocked, MRR, billing health

2. **Search and Filter**
   - API: `GET /api/customers`
   - Filters: Status, type, cohort, city, base station, date range

3. **Customer 360 View**
   - API: `GET /api/customers/{id}/360`
   - Tabs: Profile, Finance, Services, Network, Support, Projects, CRM, Timeline

4. **Profile Analysis**
   - Contact info, account details, external IDs
   - Tenure, signup date, activation date

5. **Financial Summary**
   - MRR, total invoiced, total paid, outstanding
   - Billing health: days until blocking, deposit balance
   - Recent invoices and payments

6. **Services Summary**
   - Active subscriptions, usage data
   - MRR breakdown by service

7. **Network Summary**
   - IP addresses, routers, network equipment

8. **Support Summary**
   - Open tickets, ticket history

9. **Customer Insights**
   - Page: `/customers/insights`
   - Churn risk, engagement analysis

10. **Blocked Customers**
    - Page: `/customers/blocked`
    - API: `GET /api/customers?status=blocked`
    - Review and resolve blocked accounts

---

### 17.2 Additional Customer Pages

The Customer Explorer module includes these additional pages:

**Core Pages**:
- `/customers` - Customer dashboard
- `/customers/insights` - Customer insights
- `/customers/blocked` - Blocked customers

**Analytics**:
- `/customers/analytics` - Customer analytics

**Note**: Detailed customer management (CRUD) is available at `/sales/customers/[id]`. The Customer Explorer focuses on analytics and 360-degree visibility.

---

## 18. Fleet Management Journeys

### 18.1 Vehicle Fleet Management

**Goal**: Track vehicles, drivers, insurance, and maintenance.

**Entry Point**: `/fleet`

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Fleet          │ -> │  Vehicle        │ -> │  Maintenance    │
│  Overview       │    │  Management     │    │  & Insurance    │
│                 │    │                 │    │                 │
│ /fleet          │    │ /fleet/[id]     │    │ Insurance       │
│                 │    │                 │    │ alerts          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **View Fleet Dashboard**
   - Page: `/fleet`
   - API: `GET /api/fleet/summary`
   - Shows: Total vehicles, active, insurance expiring, fleet value

2. **Vehicle List**
   - API: `GET /api/fleet/vehicles`
   - Filter by make, fuel type, status

3. **Vehicle Details**
   - Page: `/fleet/[id]`
   - API: `GET /api/fleet/vehicles/{id}`
   - License plate, driver, fuel type, odometer

4. **Insurance Monitoring**
   - API: `GET /api/fleet/insurance-expiring`
   - Track expiring insurance policies
   - Alerts for policies expiring within 30 days

5. **Fuel Type Analysis**
   - API: `GET /api/fleet/fuel-types`
   - Distribution chart by fuel type

6. **Make Analysis**
   - API: `GET /api/fleet/makes`
   - Distribution chart by vehicle make

7. **Driver Assignment**
   - API: `PATCH /api/fleet/vehicles/{id}`
   - Assign/reassign drivers to vehicles

---

## 19. Projects Journeys

### 19.1 Project Management

**Goal**: Plan, track, and deliver projects across teams.

**Entry Point**: `/projects`

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Project        │ -> │  Task           │ -> │  Completion     │
│  Creation       │    │  Management     │    │  & Analytics    │
│                 │    │                 │    │                 │
│ /projects/new   │    │ /projects/      │    │ /projects/      │
│                 │    │ tasks           │    │ analytics       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **View Projects Dashboard**
   - Page: `/projects`
   - API: `GET /api/projects/dashboard`
   - Metrics: Total projects, active, completed, tasks, avg completion

2. **Create Project**
   - Page: `/projects/new`
   - API: `POST /api/projects`
   - Fields: Name, department, priority, timeline, type

3. **Project List**
   - API: `GET /api/projects`
   - Filter by status, priority, department, type

4. **Project Details**
   - Page: `/projects/[id]`
   - API: `GET /api/projects/{id}`
   - Progress tracking, timeline, task count

5. **Task Management**
   - Page: `/projects/tasks`
   - API: `GET /api/projects/tasks`
   - All tasks across projects

6. **Task Details**
   - Page: `/projects/tasks/[id]`
   - API: `GET /api/projects/tasks/{id}`
   - Assignee, status, priority

7. **Project Analytics**
   - Page: `/projects/analytics`
   - API: `GET /api/projects/analytics`
   - Completion rates, overdue tasks

**Status Flow**:
- Open → In Progress → Completed
- Open → On Hold → Resumed → Completed
- Open → Cancelled

---

### 19.2 Additional Project Pages

The Projects module includes these additional pages:

**Core Pages**:
- `/projects` - Project dashboard
- `/projects/new` - Create project
- `/projects/[id]` - Project details

**Tasks**:
- `/projects/tasks` - Task list
- `/projects/tasks/new` - Create task
- `/projects/tasks/[id]` - Task details

**Analytics**:
- `/projects/analytics` - Project analytics

---

## 20. Reports Journeys

### 20.1 Financial Reporting

**Goal**: Access consolidated financial reports and analytics.

**Entry Point**: `/reports`

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Reports        │ -> │  Report         │ -> │  Drill-down     │
│  Overview       │    │  Selection      │    │  Analysis       │
│                 │    │                 │    │                 │
│ /reports        │    │ /reports/       │    │ Detailed        │
│                 │    │ {type}          │    │ breakdown       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Reports Dashboard**
   - Page: `/reports`
   - Shows: Revenue, Expenses, Profitability, Cash Position summaries

2. **Revenue Report**
   - Page: `/reports/revenue`
   - API: `GET /api/reports/revenue/summary`
   - Trends, customer breakdown, product analysis

3. **Expenses Report**
   - Page: `/reports/expenses`
   - API: `GET /api/reports/expenses/summary`
   - Trend analysis, vendor breakdown, category distribution

4. **Profitability Report**
   - Page: `/reports/profitability`
   - API: `GET /api/reports/profitability/margins`
   - Gross margin, net margin, segment analysis

5. **Cash Position Report**
   - Page: `/reports/cash-position`
   - API: `GET /api/reports/cash-position/summary`
   - Bank balances, forecast, runway analysis

---

## 21. Data Insights Journeys

### 21.1 Data Quality Analysis

**Goal**: Monitor data completeness, health, and relationships.

**Entry Point**: `/insights`

**Journey Flow**:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Insights       │ -> │  Completeness   │ -> │  Relationship   │
│  Overview       │    │  Analysis       │    │  Mapping        │
│                 │    │                 │    │                 │
│ /insights       │    │ /insights/      │    │ /insights/      │
│ /overview       │    │ completeness    │    │ relationships   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Steps**:

1. **Insights Overview**
   - Page: `/insights/overview`
   - High-level data quality metrics

2. **Data Completeness**
   - Page: `/insights/completeness`
   - API: `GET /api/insights/completeness`
   - Field-level completeness by entity

3. **Data Health**
   - Page: `/insights/health`
   - API: `GET /api/insights/health`
   - Validation errors, data anomalies

4. **Anomaly Detection**
   - Page: `/insights/anomalies`
   - API: `GET /api/insights/anomalies`
   - Unusual patterns in data

5. **Relationship Analysis**
   - Page: `/insights/relationships`
   - API: `GET /api/insights/relationships`
   - Entity relationship mapping

6. **Customer Segments**
   - Page: `/insights/segments`
   - API: `GET /api/insights/segments`
   - Segment distribution and analysis

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

*Document generated: 2025-12-23*
*Version: 1.1*
