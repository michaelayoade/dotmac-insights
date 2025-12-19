# Schema Prechecks

Pre-migration validation script that runs data quality checks before applying database constraint migrations.

## Purpose

This script **must pass** before running migrations that add:
- CHECK constraints
- FOREIGN KEY constraints
- NOT NULL constraints

Running prechecks prevents migration failures due to existing data violations.

## Usage

```bash
# Run all checks (basic output)
python scripts/schema_prechecks.py

# Verbose output showing each check
python scripts/schema_prechecks.py -v

# Detailed report with sample violation data
python scripts/schema_prechecks.py --report

# Custom database URL
python scripts/schema_prechecks.py --db-url "postgresql://user:pass@host/db"
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All checks passed (or only non-blocking warnings) |
| 1 | Blocking violations found - DO NOT proceed with migrations |
| 2 | Database connection error |

## Checks and Thresholds

### Blocking Checks (Must Fix)

| Check | Description | Threshold |
|-------|-------------|-----------|
| `journal_entries_balanced` | Journal entries total_debit = total_credit | 0 |
| `payments_allocation_valid` | Allocations don't exceed payment amount | 0 |
| `gl_entries_balanced` | GL entries balanced per journal | 0 |
| `invoices_positive_amounts` | No negative invoice amounts | 0 |
| `orphan_gl_entries` | GL entries have valid journal_entry_id | 0 |
| `orphan_payment_allocations` | Allocations have valid payment_id | 0 |

### Non-Blocking Checks (Warnings)

| Check | Description | Threshold |
|-------|-------------|-----------|
| `supplier_match_rate` | Purchase invoices reference valid suppliers | 0 |
| `bank_account_references` | Bank transactions reference valid accounts | 0 |
| `customers_with_email` | Active customers have email addresses | 10 |
| `unified_contacts_linked` | Customers have unified_contact_id | 0 |
| `duplicate_invoice_numbers` | No duplicate invoice numbers | 0 |

## Integration with Migrations

### Pre-Deployment Runbook

1. **Run prechecks**
   ```bash
   python scripts/schema_prechecks.py --report
   ```

2. **If blockers found**: Fix data issues before proceeding
   - Use the sample data in the report to identify specific records
   - Run corrective queries or backfill scripts
   - Re-run prechecks until clean

3. **If only warnings**: Document and proceed
   - Warnings indicate data quality issues that won't block migrations
   - Add to technical debt backlog for future cleanup

4. **Run migrations**
   ```bash
   alembic upgrade head
   ```

### CI Integration

Add to deployment pipeline:

```yaml
# .github/workflows/deploy.yml
- name: Schema Prechecks
  run: |
    python scripts/schema_prechecks.py
    if [ $? -eq 1 ]; then
      echo "::error::Schema prechecks failed - blocking violations found"
      exit 1
    fi
```

## Fixing Common Violations

### Unbalanced Journal Entries

```sql
-- Find unbalanced entries
SELECT id, posting_date, total_debit, total_credit,
       ABS(total_debit - total_credit) as difference
FROM journal_entries
WHERE ABS(total_debit - total_credit) > 0.01;

-- Option 1: Recalculate totals from GL entries
UPDATE journal_entries je
SET total_debit = (SELECT COALESCE(SUM(debit), 0) FROM gl_entries WHERE journal_entry_id = je.id),
    total_credit = (SELECT COALESCE(SUM(credit), 0) FROM gl_entries WHERE journal_entry_id = je.id)
WHERE ABS(total_debit - total_credit) > 0.01;
```

### Invalid Payment Allocations

```sql
-- Find over-allocated payments
SELECT id, amount, total_allocated, unallocated_amount
FROM payments
WHERE (total_allocated + unallocated_amount) > (amount + 0.01);

-- Option: Recalculate unallocated amount
UPDATE payments p
SET unallocated_amount = amount - total_allocated
WHERE (total_allocated + unallocated_amount) > (amount + 0.01);
```

### Orphan GL Entries

```sql
-- Find orphan GL entries (no parent journal)
SELECT ge.id, ge.journal_entry_id
FROM gl_entries ge
WHERE NOT EXISTS (
    SELECT 1 FROM journal_entries je WHERE je.id = ge.journal_entry_id
);

-- Option: Delete orphans (CAUTION - verify first!)
-- DELETE FROM gl_entries WHERE journal_entry_id NOT IN (SELECT id FROM journal_entries);
```

### Missing Unified Contact Links

```sql
-- Run the backfill script instead
python scripts/backfill_unified_contacts.py --dry-run
python scripts/backfill_unified_contacts.py
```

## Adding New Checks

Edit `scripts/schema_prechecks.py` and add to the `CHECKS` list:

```python
{
    "name": "my_new_check",
    "description": "Human-readable description of what this checks",
    "query": """
        SELECT COUNT(*) FROM my_table
        WHERE some_condition
    """,
    "threshold": 0,  # Maximum allowed violations
    "blocker": True,  # True = must fix, False = warning only
    "sample_query": """
        SELECT id, relevant_columns FROM my_table
        WHERE some_condition
        LIMIT 10
    """,
}
```

## Migration Notes (2025-12-18)

### Indexes (CONCURRENTLY)

All index migrations now use `CREATE INDEX CONCURRENTLY` with transaction break (`op.execute("COMMIT")`) to avoid table locks:

| Index | Table | Columns |
|-------|-------|---------|
| `ix_journal_entries_posting_date` | journal_entries | posting_date |
| `ix_gl_entries_account_posting` | gl_entries | account, posting_date |
| `ix_invoices_customer_posting` | invoices | customer_id, invoice_date |
| `ix_invoices_status_posting` | invoices | status, invoice_date |
| `ix_invoices_due_date` | invoices | due_date (partial: balance > 0) |
| `ix_bank_transactions_account_date` | bank_transactions | bank_account, date |
| `ix_bank_transactions_unreconciled` | bank_transactions | date (partial: UNRECONCILED) |
| `ix_projects_status` | projects | status |
| `ix_projects_customer` | projects | customer_id (partial: NOT NULL) |

### FK Migrations (Backfill + NOT VALID/VALIDATE)

FK migrations follow the safe pattern:
1. Add nullable FK column
2. Backfill from existing string column
3. Create index CONCURRENTLY
4. Add FK constraint as NOT VALID (instant)
5. Separate VALIDATE migration (scans but doesn't lock)

| FK Column | Table | Backfill Source |
|-----------|-------|-----------------|
| `supplier_id` | purchase_invoices | `supplier` → suppliers.name/erpnext_id |
| `bank_account_id` | bank_transactions | `bank_account` → bank_accounts.name/account_number |
| `customer_id` | erpnext_leads | `customer` → customers.name/erpnext_id + email match |

### CHECK Constraints Applied

| Constraint | Table | Condition |
|------------|-------|-----------|
| `chk_journal_entry_balanced` | journal_entries | `ABS(total_debit - total_credit) < 0.01` |
| `chk_payment_allocation_valid` | payments | Allocation <= amount (refunds exempt) |
| `chk_invoice_positive` | invoices | `amount >= 0, total_amount >= 0, balance >= 0` |

### Non-Blocking Warnings (Pending)

| Issue | Count | Resolution |
|-------|-------|------------|
| Customers without email | 216 | Data quality - review in CRM |
| Customers without unified_contact_id | 4423 | Run contacts backfill (Phase 4.2) |

## Related Files

- `alembic/versions/20251218_add_checks_not_valid.py` - CHECK constraint migration (NOT VALID)
- `alembic/versions/20251218_validate_checks.py` - VALIDATE CHECK constraints
- `alembic/versions/20251218_idx_*.py` - Index migrations (CONCURRENTLY)
- `alembic/versions/20251218_fix_service_token_fk.py` - ServiceToken FK fix
- `alembic/versions/20251218_add_supplier_fk.py` - Supplier FK with backfill (NOT VALID)
- `alembic/versions/20251218_add_bank_account_fk.py` - Bank account FK with backfill (NOT VALID)
- `alembic/versions/20251218_add_erpnext_lead_customer_fk.py` - Lead customer FK with backfill (NOT VALID)
- `alembic/versions/20251218_validate_fks.py` - VALIDATE FK constraints
- `scripts/backfill_unified_contacts.py` - Contacts backfill script
- `scripts/backfill_unified_tickets.py` - Tickets backfill script
