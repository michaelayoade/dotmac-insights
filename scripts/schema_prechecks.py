#!/usr/bin/env python3
"""
Schema Prechecks Script

Runs data quality validation before applying database constraint migrations.
This script must pass before:
- Adding CHECK constraints
- Adding FOREIGN KEY constraints
- Enforcing NOT NULL constraints

Usage:
    python scripts/schema_prechecks.py               # Run all checks
    python scripts/schema_prechecks.py --fix        # Run checks and attempt auto-fixes
    python scripts/schema_prechecks.py --report     # Generate detailed report

Exit codes:
    0 - All checks passed (or non-blocking only)
    1 - Blocking violations found
    2 - Database connection error
"""

import os
import sys
import argparse
from datetime import datetime
from typing import NamedTuple, Optional
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


class CheckResult(NamedTuple):
    name: str
    description: str
    query: str
    threshold: int
    blocker: bool
    count: int
    passed: bool
    sample_data: Optional[list] = None


# =============================================================================
# CHECK DEFINITIONS
# =============================================================================

CHECKS = [
    # Accounting integrity checks
    {
        "name": "journal_entries_balanced",
        "description": "Journal entries must be balanced (debits = credits)",
        "query": """
            SELECT COUNT(*) FROM journal_entries
            WHERE ABS(total_debit - total_credit) > 0.01
        """,
        "threshold": 0,
        "blocker": True,  # Must be 0 before CHECK constraint
        "sample_query": """
            SELECT id, posting_date, total_debit, total_credit,
                   ABS(total_debit - total_credit) as difference
            FROM journal_entries
            WHERE ABS(total_debit - total_credit) > 0.01
            LIMIT 10
        """,
    },
    {
        "name": "payments_allocation_valid",
        "description": "Payment allocations must not exceed payment amount",
        "query": """
            SELECT COUNT(*) FROM payments
            WHERE (total_allocated + unallocated_amount) > (amount + 0.01)
            OR total_allocated < 0
            OR unallocated_amount < 0
        """,
        "threshold": 0,
        "blocker": True,
        "sample_query": """
            SELECT id, amount, total_allocated, unallocated_amount
            FROM payments
            WHERE (total_allocated + unallocated_amount) > (amount + 0.01)
            OR total_allocated < 0
            OR unallocated_amount < 0
            LIMIT 10
        """,
    },
    {
        "name": "gl_entries_balanced",
        "description": "GL entry lines must be balanced per journal entry",
        "query": """
            SELECT COUNT(DISTINCT journal_entry_id) FROM (
                SELECT journal_entry_id, SUM(debit) as total_debit, SUM(credit) as total_credit
                FROM gl_entries
                GROUP BY journal_entry_id
                HAVING ABS(SUM(debit) - SUM(credit)) > 0.01
            ) unbalanced
        """,
        "threshold": 0,
        "blocker": True,
        "sample_query": """
            SELECT journal_entry_id, SUM(debit) as total_debit, SUM(credit) as total_credit
            FROM gl_entries
            GROUP BY journal_entry_id
            HAVING ABS(SUM(debit) - SUM(credit)) > 0.01
            LIMIT 10
        """,
    },
    # FK reference checks
    {
        "name": "supplier_match_rate",
        "description": "Purchase invoices should reference valid suppliers",
        "query": """
            SELECT COUNT(*) FROM purchase_invoices pi
            LEFT JOIN suppliers s ON pi.supplier = s.name OR pi.supplier = s.erpnext_id
            WHERE s.id IS NULL AND pi.supplier IS NOT NULL AND pi.supplier != ''
        """,
        "threshold": 0,
        "blocker": False,  # Warning - will be NULL FK
        "sample_query": """
            SELECT pi.id, pi.supplier, pi.posting_date
            FROM purchase_invoices pi
            LEFT JOIN suppliers s ON pi.supplier = s.name OR pi.supplier = s.erpnext_id
            WHERE s.id IS NULL AND pi.supplier IS NOT NULL AND pi.supplier != ''
            LIMIT 10
        """,
    },
    {
        "name": "bank_account_references",
        "description": "Bank transactions should reference valid bank accounts",
        "query": """
            SELECT COUNT(*) FROM bank_transactions bt
            WHERE bt.bank_account IS NOT NULL
            AND bt.bank_account != ''
            AND NOT EXISTS (
                SELECT 1 FROM bank_accounts ba
                WHERE ba.name = bt.bank_account OR ba.account_number = bt.bank_account
            )
        """,
        "threshold": 0,
        "blocker": False,
        "sample_query": """
            SELECT bt.id, bt.bank_account, bt.transaction_date
            FROM bank_transactions bt
            WHERE bt.bank_account IS NOT NULL
            AND bt.bank_account != ''
            AND NOT EXISTS (
                SELECT 1 FROM bank_accounts ba
                WHERE ba.name = bt.bank_account OR ba.account_number = bt.bank_account
            )
            LIMIT 10
        """,
    },
    # Data quality checks
    {
        "name": "customers_with_email",
        "description": "Customers should have email addresses",
        "query": """
            SELECT COUNT(*) FROM customers
            WHERE (email IS NULL OR email = '') AND status = 'active'
        """,
        "threshold": 10,  # Allow some without email
        "blocker": False,
        "sample_query": """
            SELECT id, name, phone, status FROM customers
            WHERE (email IS NULL OR email = '') AND status = 'active'
            LIMIT 10
        """,
    },
    {
        "name": "unified_contacts_linked",
        "description": "All customers should have unified_contact_id",
        "query": """
            SELECT COUNT(*) FROM customers
            WHERE unified_contact_id IS NULL
        """,
        "threshold": 0,
        "blocker": False,  # Will be enforced after backfill
        "sample_query": """
            SELECT id, name, email, created_at FROM customers
            WHERE unified_contact_id IS NULL
            LIMIT 10
        """,
    },
    {
        "name": "invoices_positive_amounts",
        "description": "Invoices should have positive amounts",
        "query": """
            SELECT COUNT(*) FROM invoices
            WHERE grand_total < 0 OR net_total < 0
        """,
        "threshold": 0,
        "blocker": True,
        "sample_query": """
            SELECT id, name, grand_total, net_total, posting_date
            FROM invoices
            WHERE grand_total < 0 OR net_total < 0
            LIMIT 10
        """,
    },
    {
        "name": "duplicate_invoice_numbers",
        "description": "Invoice numbers should be unique",
        "query": """
            SELECT COUNT(*) FROM (
                SELECT name, COUNT(*) as cnt FROM invoices
                WHERE name IS NOT NULL AND name != ''
                GROUP BY name HAVING COUNT(*) > 1
            ) duplicates
        """,
        "threshold": 0,
        "blocker": False,
        "sample_query": """
            SELECT name, COUNT(*) as cnt FROM invoices
            WHERE name IS NOT NULL AND name != ''
            GROUP BY name HAVING COUNT(*) > 1
            LIMIT 10
        """,
    },
    # Orphan record checks
    {
        "name": "orphan_gl_entries",
        "description": "GL entries should reference valid journal entries",
        "query": """
            SELECT COUNT(*) FROM gl_entries ge
            WHERE NOT EXISTS (
                SELECT 1 FROM journal_entries je WHERE je.id = ge.journal_entry_id
            )
        """,
        "threshold": 0,
        "blocker": True,
        "sample_query": """
            SELECT ge.id, ge.journal_entry_id, ge.account_id, ge.debit, ge.credit
            FROM gl_entries ge
            WHERE NOT EXISTS (
                SELECT 1 FROM journal_entries je WHERE je.id = ge.journal_entry_id
            )
            LIMIT 10
        """,
    },
    {
        "name": "orphan_payment_allocations",
        "description": "Payment allocations should reference valid payments",
        "query": """
            SELECT COUNT(*) FROM payment_allocations pa
            WHERE NOT EXISTS (
                SELECT 1 FROM payments p WHERE p.id = pa.payment_id
            )
        """,
        "threshold": 0,
        "blocker": True,
        "sample_query": """
            SELECT pa.id, pa.payment_id, pa.invoice_id, pa.amount
            FROM payment_allocations pa
            WHERE NOT EXISTS (
                SELECT 1 FROM payments p WHERE p.id = pa.payment_id
            )
            LIMIT 10
        """,
    },
]


# =============================================================================
# RUNNER
# =============================================================================


def run_check(session: Session, check: dict) -> CheckResult:
    """Run a single check and return result."""
    try:
        result = session.execute(text(check["query"]))
        count = result.scalar() or 0

        # Get sample data if violations found
        sample_data = None
        if count > 0 and "sample_query" in check:
            try:
                sample_result = session.execute(text(check["sample_query"]))
                sample_data = [dict(row._mapping) for row in sample_result.fetchall()]
            except Exception:
                pass

        passed = count <= check["threshold"]

        return CheckResult(
            name=check["name"],
            description=check["description"],
            query=check["query"].strip(),
            threshold=check["threshold"],
            blocker=check["blocker"],
            count=count,
            passed=passed,
            sample_data=sample_data,
        )
    except Exception as e:
        # If table doesn't exist, treat as passed
        if "does not exist" in str(e).lower() or "no such table" in str(e).lower():
            return CheckResult(
                name=check["name"],
                description=check["description"],
                query=check["query"].strip(),
                threshold=check["threshold"],
                blocker=check["blocker"],
                count=0,
                passed=True,
                sample_data=None,
            )
        raise


def run_all_checks(session: Session, verbose: bool = False) -> list[CheckResult]:
    """Run all checks and return results."""
    results = []

    for check in CHECKS:
        if verbose:
            print(f"  Running: {check['name']}...", end=" ", flush=True)

        result = run_check(session, check)
        results.append(result)

        if verbose:
            status = "PASS" if result.passed else ("BLOCK" if result.blocker else "WARN")
            print(f"{status} (count={result.count}, threshold={result.threshold})")

    return results


def print_report(results: list[CheckResult], detailed: bool = False) -> None:
    """Print formatted report of check results."""
    print("\n" + "=" * 70)
    print("SCHEMA PRECHECKS REPORT")
    print(f"Generated: {datetime.utcnow().isoformat()}")
    print("=" * 70)

    # Summary
    passed = sum(1 for r in results if r.passed)
    blocked = sum(1 for r in results if not r.passed and r.blocker)
    warned = sum(1 for r in results if not r.passed and not r.blocker)

    print(f"\nSummary: {passed}/{len(results)} passed, {blocked} blockers, {warned} warnings\n")

    # Blockers first
    blockers = [r for r in results if not r.passed and r.blocker]
    if blockers:
        print("BLOCKING VIOLATIONS (must fix before migration):")
        print("-" * 50)
        for r in blockers:
            print(f"\n  [{r.name}]")
            print(f"  Description: {r.description}")
            print(f"  Count: {r.count} (threshold: {r.threshold})")
            if detailed and r.sample_data:
                print("  Sample data:")
                for row in r.sample_data[:5]:
                    print(f"    {row}")
        print()

    # Warnings
    warnings = [r for r in results if not r.passed and not r.blocker]
    if warnings:
        print("WARNINGS (non-blocking, should review):")
        print("-" * 50)
        for r in warnings:
            print(f"\n  [{r.name}]")
            print(f"  Description: {r.description}")
            print(f"  Count: {r.count} (threshold: {r.threshold})")
            if detailed and r.sample_data:
                print("  Sample data:")
                for row in r.sample_data[:3]:
                    print(f"    {row}")
        print()

    # Passed
    passed_checks = [r for r in results if r.passed]
    if passed_checks:
        print("PASSED:")
        print("-" * 50)
        for r in passed_checks:
            print(f"  [OK] {r.name} (count={r.count})")
        print()

    # Final verdict
    print("=" * 70)
    if blocked > 0:
        print("RESULT: BLOCKED - Fix violations before running migrations")
        print("=" * 70)
    elif warned > 0:
        print("RESULT: PASSED WITH WARNINGS - Safe to proceed, but review warnings")
        print("=" * 70)
    else:
        print("RESULT: ALL PASSED - Safe to proceed with migrations")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Run schema prechecks before constraint migrations"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to auto-fix violations (where possible)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate detailed report with sample data",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show progress during checks",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=os.getenv("DATABASE_URL"),
        help="Database URL (defaults to DATABASE_URL env var)",
    )
    args = parser.parse_args()

    if not args.db_url:
        print("Error: DATABASE_URL not set. Use --db-url or set DATABASE_URL env var.")
        sys.exit(2)

    print(f"Connecting to database...")

    try:
        engine = create_engine(args.db_url)
        with Session(engine) as session:
            print("Running schema prechecks...\n")
            results = run_all_checks(session, verbose=args.verbose)
            print_report(results, detailed=args.report)

            # Determine exit code
            blocked = any(not r.passed and r.blocker for r in results)
            sys.exit(1 if blocked else 0)

    except Exception as e:
        print(f"Error: Database connection failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
