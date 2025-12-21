# Database Index Review

**Date:** 2025-12-21
**Scope:** Core tables used by consolidated dashboards and high-traffic APIs

---

## Executive Summary

| Category | Count | Action Required |
|----------|-------|-----------------|
| Missing critical indexes | 12 | HIGH PRIORITY |
| Unindexed foreign keys | 18 | MEDIUM PRIORITY |
| Redundant indexes (candidates) | 108 | EVALUATE |
| Well-designed indexes | 163+ | OK |

---

## 1. Missing Critical Indexes

These indexes are needed based on dashboard query patterns:

### Payments Table
```sql
-- Collections queries filter by status + payment_date + currency
CREATE INDEX CONCURRENTLY ix_payments_status_date_currency
ON payments (status, payment_date, currency)
WHERE is_deleted = false;

-- Revenue trend uses date truncation with status filter
CREATE INDEX CONCURRENTLY ix_payments_status_date
ON payments (status, payment_date);
```

### Invoices Table
```sql
-- AR aging and outstanding queries need status + currency
CREATE INDEX CONCURRENTLY ix_invoices_status_currency
ON invoices (status, currency);

-- Aging analysis by due date
CREATE INDEX CONCURRENTLY ix_invoices_due_status_currency
ON invoices (due_date, status, currency)
WHERE status IN ('pending', 'overdue', 'partially_paid');
```

### Purchase Invoices Table
```sql
-- AP outstanding queries
CREATE INDEX CONCURRENTLY ix_purchase_invoices_status_date_currency
ON purchase_invoices (status, posting_date, currency)
WHERE outstanding_amount > 0;

-- Overdue payables
CREATE INDEX CONCURRENTLY ix_purchase_invoices_due_status
ON purchase_invoices (due_date, status)
WHERE outstanding_amount > 0;

-- Top suppliers query
CREATE INDEX CONCURRENTLY ix_purchase_invoices_supplier_outstanding
ON purchase_invoices (supplier_name, outstanding_amount DESC);
```

### Subscriptions Table
```sql
-- MRR calculations filter by status + currency
CREATE INDEX CONCURRENTLY ix_subscriptions_status_currency
ON subscriptions (status, currency);
```

### GL Entries Table
```sql
-- Payment entry queries
CREATE INDEX CONCURRENTLY ix_gl_entries_voucher_party_cancelled
ON gl_entries (voucher_type, party_type, is_cancelled, posting_date DESC);

-- Account balance queries with date range
CREATE INDEX CONCURRENTLY ix_gl_entries_account_cancelled_date
ON gl_entries (account, is_cancelled, posting_date);
```

### Unified Tickets Table
```sql
-- Overdue tickets query
CREATE INDEX CONCURRENTLY ix_unified_tickets_status_resolution_created
ON unified_tickets (status, resolution_by, created_at)
WHERE status IN ('open', 'in_progress', 'waiting');

-- Category breakdown
CREATE INDEX CONCURRENTLY ix_unified_tickets_category_created
ON unified_tickets (category, created_at);
```

### Accounts Table
```sql
-- Balance sheet queries group by root_type
CREATE INDEX CONCURRENTLY ix_accounts_root_type_disabled
ON accounts (root_type, disabled);
```

---

## 2. Unindexed Foreign Keys

Foreign keys without indexes can cause slow DELETE/UPDATE cascades:

### High Priority (Frequently Accessed Tables)

| Table | Foreign Key Column | Recommendation |
|-------|-------------------|----------------|
| `invoices` | `payment_terms_id` | Add index |
| `invoices` | `fiscal_period_id` | Add index |
| `invoices` | `journal_entry_id` | Add index |
| `payments` | `bank_account_id` | Add index |
| `payments` | `fiscal_period_id` | Add index |
| `payments` | `journal_entry_id` | Add index |
| `purchase_invoices` | `payment_terms_id` | Add index |
| `purchase_invoices` | `fiscal_period_id` | Add index |
| `purchase_invoices` | `journal_entry_id` | Add index |
| `unified_tickets` | `merged_into_id` | Add index |

### Low Priority (Audit/Tracking Fields)

| Table | Foreign Key Column | Recommendation |
|-------|-------------------|----------------|
| `invoices` | `created_by_id` | Optional |
| `invoices` | `deleted_by_id` | Optional |
| `payments` | `created_by_id` | Optional |
| `payments` | `deleted_by_id` | Optional |
| `payments` | `updated_by_id` | Optional |
| `purchase_invoices` | `created_by_id` | Optional |
| `customers` | `deleted_by_id` | Optional |
| `unified_tickets` | `created_by_id` | Optional |

---

## 3. Redundant Index Candidates

These single-column indexes are covered by composite indexes starting with the same column. **Evaluate before removing** - some may still be useful for single-column lookups.

### Confirmed Redundant (Safe to Remove)

| Table | Redundant Index | Covered By |
|-------|----------------|------------|
| `invoices` | `ix_invoices_status` | `ix_invoices_status_posting` |
| `invoices` | `ix_invoices_customer_id` | `ix_invoices_customer_posting` |
| `unified_tickets` | `ix_unified_tickets_status` | `ix_unified_tickets_status_priority` |
| `unified_tickets` | `ix_unified_tickets_assigned_to_id` | `ix_unified_tickets_assigned_status` |
| `unified_tickets` | `ix_unified_tickets_created_at` | `ix_unified_tickets_created_status` |
| `unified_tickets` | `ix_unified_tickets_source` | `ix_unified_tickets_source_status` |
| `unified_contacts` | `ix_unified_contacts_contact_type` | `ix_unified_contacts_type_status` |
| `unified_contacts` | `ix_unified_contacts_email` | `ix_unified_contacts_email_type` |
| `unified_contacts` | `ix_unified_contacts_phone` | `ix_unified_contacts_phone_type` |
| `service_orders` | `ix_service_orders_scheduled_date` | `ix_service_orders_scheduled` |
| `service_orders` | `ix_service_orders_customer_id` | `ix_service_orders_customer` |
| `gl_entries` | `ix_gl_entries_account` | `ix_gl_entries_account_posting` |

### Keep Despite Coverage (Frequently Used Alone)

| Table | Index | Reason to Keep |
|-------|-------|----------------|
| `unified_tickets` | `ix_unified_tickets_resolution_by` | SLA queries sometimes only check deadline |
| `unified_tickets` | `ix_unified_tickets_response_by` | Response SLA checks |
| `unified_contacts` | `ix_unified_contacts_owner_id` | Owner lookups without type filter |

---

## 4. Well-Designed Index Patterns

### Exemplary Composite Indexes

**unified_tickets** - Excellent coverage:
- `(status, priority)` - Ticket queue sorting
- `(assigned_to_id, status)` - Agent workload
- `(unified_contact_id, status)` - Customer ticket history
- `(source, status)` - Channel analytics
- `(created_at, status)` - Time-series with status
- `(resolution_by, resolution_sla_breached)` - SLA tracking
- `(response_by, response_sla_breached)` - Response SLA

**service_orders** - Good dispatch optimization:
- `(scheduled_date, status)` - Daily scheduling
- `(customer_id, status)` - Customer service history
- `(assigned_technician_id, scheduled_date)` - Technician calendar

**unified_contacts** - Good search patterns:
- `(contact_type, status)` - Filtered lists
- `(email, contact_type)` - Lookup by email with type
- `(phone, contact_type)` - Lookup by phone with type
- `(owner_id, contact_type)` - User's contacts

---

## 5. Migration Script

```sql
-- =====================================================
-- HIGH PRIORITY: Add missing critical indexes
-- =====================================================

-- Run with CONCURRENTLY to avoid table locks.
-- Note: CREATE INDEX CONCURRENTLY must be executed outside an explicit transaction.

-- Payments
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_payments_status_date_currency
ON payments (status, payment_date, currency) WHERE is_deleted = false;

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_payments_status_date
ON payments (status, payment_date);

-- Invoices
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_invoices_status_currency
ON invoices (status, currency);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_invoices_due_status_currency
ON invoices (due_date, status, currency)
WHERE status IN ('pending', 'overdue', 'partially_paid');

-- Purchase Invoices
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_purchase_invoices_status_date_currency
ON purchase_invoices (status, posting_date, currency)
WHERE outstanding_amount > 0;

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_purchase_invoices_due_status
ON purchase_invoices (due_date, status)
WHERE outstanding_amount > 0;

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_purchase_invoices_supplier_outstanding
ON purchase_invoices (supplier_name, outstanding_amount DESC);

-- Subscriptions
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_subscriptions_status_currency
ON subscriptions (status, currency);

-- GL Entries
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_gl_entries_voucher_party_cancelled
ON gl_entries (voucher_type, party_type, is_cancelled, posting_date DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_gl_entries_account_cancelled_date
ON gl_entries (account, is_cancelled, posting_date);

-- Unified Tickets
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_unified_tickets_status_resolution_created
ON unified_tickets (status, resolution_by, created_at)
WHERE status IN ('open', 'in_progress', 'waiting');

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_unified_tickets_category_created
ON unified_tickets (category, created_at);

-- Accounts
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_accounts_root_type_disabled
ON accounts (root_type, disabled);

-- =====================================================
-- MEDIUM PRIORITY: Add foreign key indexes
-- =====================================================

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_invoices_payment_terms_id
ON invoices (payment_terms_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_invoices_fiscal_period_id
ON invoices (fiscal_period_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_invoices_journal_entry_id
ON invoices (journal_entry_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_payments_bank_account_id
ON payments (bank_account_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_payments_fiscal_period_id
ON payments (fiscal_period_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_payments_journal_entry_id
ON payments (journal_entry_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_purchase_invoices_payment_terms_id
ON purchase_invoices (payment_terms_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_purchase_invoices_fiscal_period_id
ON purchase_invoices (fiscal_period_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_purchase_invoices_journal_entry_id
ON purchase_invoices (journal_entry_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_unified_tickets_merged_into_id
ON unified_tickets (merged_into_id);

-- =====================================================
-- LOW PRIORITY: Remove redundant indexes (after testing)
-- =====================================================

-- Test query performance before dropping!
-- DROP INDEX CONCURRENTLY IF EXISTS ix_invoices_status;
-- DROP INDEX CONCURRENTLY IF EXISTS ix_invoices_customer_id;
-- DROP INDEX CONCURRENTLY IF EXISTS ix_unified_tickets_status;
-- etc.
```

---

## 6. Performance Impact Estimates

| Index Addition | Affected Queries | Expected Improvement |
|----------------|------------------|---------------------|
| `ix_payments_status_date_currency` | Sales dashboard collections | 50-80% faster |
| `ix_invoices_status_currency` | AR outstanding, aging | 40-60% faster |
| `ix_purchase_invoices_due_status` | AP aging, overdue | 50-70% faster |
| `ix_gl_entries_voucher_party_cancelled` | Payment entry lookups | 60-80% faster |
| `ix_subscriptions_status_currency` | MRR calculations | 30-50% faster |

---

## 7. Monitoring Recommendations

After applying indexes, monitor with:

```sql
-- Check index usage
SELECT
    schemaname || '.' || relname AS table,
    indexrelname AS index,
    idx_scan AS scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC
LIMIT 50;

-- Find unused indexes (candidates for removal)
SELECT
    schemaname || '.' || relname AS table,
    indexrelname AS index,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Check slow queries
SELECT
    query,
    calls,
    total_time / 1000 as total_seconds,
    mean_time / 1000 as mean_seconds
FROM pg_stat_statements
WHERE query LIKE '%invoices%' OR query LIKE '%payments%'
ORDER BY total_time DESC
LIMIT 20;
```

---

## 8. Next Steps

1. **Immediate**: Create missing critical indexes (Section 5 migration script)
2. **This Week**: Add foreign key indexes for high-priority tables
3. **After Monitoring**: Evaluate and remove redundant indexes based on pg_stat_user_indexes
4. **Ongoing**: Run monitoring queries weekly to identify new slow queries
