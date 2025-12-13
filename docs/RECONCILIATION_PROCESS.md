# Dotmac Account Reconciliation Process

## Executive Summary

**Current Issues Identified:**
| Issue | Amount | Priority |
|-------|--------|----------|
| Negative bank balances (GL) | N30.7M | Critical |
| Unreconciled bank transactions | N187M | High |
| Unallocated payments | N78M | High |
| AR vs Outstanding Invoice gap | N70M | Medium |

---

## Phase 1: Bank Statement Reconciliation (Week 1-2)

### Objective
Match every bank transaction in ERPNext with its corresponding Payment Entry or Journal Entry.

### Process

#### Step 1.1: Export Unreconciled Transactions
1. Go to **Bank Reconciliation Tool** (`/app/bank-reconciliation-tool`)
2. Select each bank account one at a time
3. Set date range (start with January 2025, work forward)
4. Export unreconciled transactions to Excel

#### Step 1.2: Reconcile by Bank Account (Priority Order)

| Bank Account | Unreconciled | Action |
|--------------|-------------|--------|
| Zenith 523 | N73M (27 txns) | Start here - largest amount, fewest transactions |
| UBA | N27M (37 txns) | Second priority |
| Zenith 461 | N32M (451 txns) | Third - many small transactions |
| Paystack | N39M (1,262 txns) | Fourth - high volume |
| Paystack OPEX | N16M (1,531 txns) | Last - mostly small expenses |

#### Step 1.3: For Each Unreconciled Transaction

**If Payment Entry exists:**
1. Open Bank Reconciliation Tool
2. Select the bank transaction
3. Search for matching Payment Entry by amount/date
4. Click "Reconcile"

**If Payment Entry missing:**
1. Check if payment was recorded in Splynx but not pushed to ERPNext
2. Create Payment Entry manually with correct:
   - Customer/Supplier
   - Amount
   - Date
   - Bank account
   - Reference number from bank statement
3. Then reconcile

**If it's an Internal Transfer:**
1. Check if Journal Entry exists for inter-bank transfer
2. If not, create Journal Entry (Bank Entry type)
3. Reconcile both sides (debit and credit banks)

#### Step 1.4: Daily Checklist
- [ ] Select one bank account
- [ ] Reconcile all transactions for one month
- [ ] Verify bank GL balance matches bank statement
- [ ] Document any discrepancies found
- [ ] Move to next month

---

## Phase 2: Payment-to-Invoice Reconciliation (Week 2-3)

### Objective
Allocate all customer payments to their corresponding invoices.

### Process

#### Step 2.1: Identify Unallocated Payments
1. Go to **Payment Reconciliation** (`/app/payment-reconciliation`)
2. Select Party Type: Customer
3. Filter by customers with unallocated amounts
4. Export list to Excel

#### Step 2.2: For Each Unallocated Payment

**Automatic Matching:**
1. Open Payment Reconciliation for the customer
2. System shows unallocated payments and outstanding invoices
3. If amounts match, click "Allocate"
4. System will link payment to invoice

**Manual Matching (partial payments):**
1. If payment covers multiple invoices:
   - Allocate to oldest invoices first (FIFO)
   - Enter allocation amount for each invoice
2. If payment is partial:
   - Allocate full payment amount to one invoice
   - Invoice will show remaining outstanding

**Payment with no matching invoice:**
1. Check Splynx for the invoice
2. If invoice exists in Splynx but not ERPNext:
   - Run invoice sync
   - Then allocate payment
3. If advance payment (no invoice yet):
   - Leave unallocated
   - Tag with note "Advance payment"

#### Step 2.3: Priority Customers (Top Outstanding)

| Customer | Outstanding | Action |
|----------|-------------|--------|
| National Health Insurance Authority | N83.6M | Verify contract, check for payments |
| SON (Abuja Corporate) | N59M | 10 invoices - reconcile each |
| Tax Appeal Tribunal | N22M | Single invoice - follow up |
| PTAD | N16.8M | Has N5M payment - allocate |
| Norrenberger Financial Group | N7.3M | Has N3.2M payments - allocate |

---

## Phase 3: GL Account Reconciliation (Week 3-4)

### Objective
Ensure GL balances match subledger totals and correct any discrepancies.

### Process

#### Step 3.1: Fix Negative Bank Balances

**Root Cause:** Payments recorded without matching bank deposits

| Bank Account | Negative Balance | Action |
|--------------|-----------------|--------|
| Zenith 461 | -N18.1M | Find missing deposits |
| Zenith 523 | -N10.4M | Find missing deposits |
| Paystack | -N2.2M | Check Paystack settlements |

**Steps to Fix:**
1. Go to General Ledger (`/app/general-ledger`)
2. Filter by bank account
3. Export all entries
4. Compare with bank statement
5. Identify missing deposit entries
6. Create Journal Entries for missing deposits

#### Step 3.2: Reconcile AR Balance

**Current Gap:** N70M difference between AR GL and Outstanding Invoices

| Check | Expected |
|-------|----------|
| AR GL Balance | Should equal sum of outstanding invoices |
| If AR GL > Outstanding | Payments not linked to invoices |
| If AR GL < Outstanding | Invoices not posted to GL |

**Steps:**
1. Run Accounts Receivable report (`/app/query-report/Accounts Receivable`)
2. Compare total with GL balance
3. Investigate differences by customer
4. Fix any posting errors

#### Step 3.3: Monthly Close Checklist
- [ ] Bank GL = Bank Statement (for each bank)
- [ ] AR GL = Sum of Outstanding Invoices
- [ ] AP GL = Sum of Outstanding Bills
- [ ] All payments allocated to invoices
- [ ] All bank transactions reconciled

---

## Phase 4: Ongoing Process (Monthly)

### Weekly Tasks
| Day | Task |
|-----|------|
| Monday | Reconcile previous week's bank transactions |
| Wednesday | Allocate new payments to invoices |
| Friday | Review unreconciled items, escalate issues |

### Monthly Close (By 5th of following month)
1. **Bank Reconciliation**
   - All banks reconciled for previous month
   - Bank statements obtained and filed

2. **Payment Reconciliation**
   - All payments allocated
   - Advance payments tagged

3. **AR Review**
   - Outstanding invoices aging report
   - Follow up on 60+ day items

4. **GL Verification**
   - Trial balance review
   - Bank balances verified
   - AR/AP subledger match

---

## Tools & Reports

### ERPNext Tools
| Tool | Location | Purpose |
|------|----------|---------|
| Bank Reconciliation Tool | `/app/bank-reconciliation-tool` | Match bank txns |
| Payment Reconciliation | `/app/payment-reconciliation` | Allocate payments |
| General Ledger | `/app/general-ledger` | View GL entries |
| Trial Balance | `/app/trial-balance` | Account balances |
| Accounts Receivable | `/app/query-report/Accounts Receivable` | AR aging |

### Key Reports
1. **Bank Reconciliation Statement** - Shows reconciled vs unreconciled
2. **Accounts Receivable Aging** - Outstanding by customer/age
3. **Payment Ledger** - All payments with allocation status
4. **General Ledger** - Detailed GL transactions

---

## Escalation Matrix

| Issue | First Contact | Escalation | Timeline |
|-------|--------------|------------|----------|
| Missing bank transaction | Accountant | Finance Manager | 2 days |
| Large unallocated payment (>N1M) | Finance Manager | CFO | 1 day |
| GL discrepancy | Senior Accountant | Finance Manager | 3 days |
| Negative bank balance | Finance Manager | CFO | Immediate |

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Bank transactions reconciled | 100% | 91% |
| Payments allocated to invoices | 100% | ~75% |
| Negative bank balances | N0 | -N30.7M |
| AR GL vs Subledger difference | <N100K | N70M |

---

## Appendix: Common Issues & Solutions

### Issue 1: Payment in ERPNext but not in bank
**Cause:** Payment entry created incorrectly or duplicate
**Solution:** Cancel incorrect payment entry, recreate with correct details

### Issue 2: Bank deposit with no payment entry
**Cause:** Payment recorded in Splynx but not synced
**Solution:** Check Splynx, create payment entry, then reconcile

### Issue 3: Bulk payment covering multiple invoices
**Cause:** Corporate client pays one lump sum
**Solution:** Use Payment Reconciliation to split across invoices

### Issue 4: Internal transfer not reconciled
**Cause:** Missing Journal Entry for inter-bank transfer
**Solution:** Create Bank Entry Journal Entry, reconcile both banks

### Issue 5: Foreign currency transactions
**Cause:** USD transactions need exchange rate
**Solution:** Create multi-currency Journal Entry with correct rates
