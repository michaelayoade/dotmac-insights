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

## Related Files

- `alembic/versions/20251218_add_checks_not_valid.py` - CHECK constraint migration
- `alembic/versions/20251218_validate_checks.py` - VALIDATE constraint migration
- `scripts/backfill_unified_contacts.py` - Contacts backfill script
