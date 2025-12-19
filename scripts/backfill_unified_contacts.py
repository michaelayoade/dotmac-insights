#!/usr/bin/env python3
"""
Backfill script for unified_contact_id

This script ensures all contact-related records have unified_contact_id populated.
Run this BEFORE the enforce-not-null migration.

Usage:
    # Dry run - show what would be updated
    python scripts/backfill_unified_contacts.py --dry-run

    # Actually perform the backfill
    python scripts/backfill_unified_contacts.py

    # Check status only
    python scripts/backfill_unified_contacts.py --status
"""
import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.services.unified_contact_enforcement import UnifiedContactEnforcement


def get_orphan_counts(session) -> dict[str, int]:
    """Get count of records missing unified_contact_id."""
    queries = {
        "customers": "SELECT COUNT(*) FROM customers WHERE unified_contact_id IS NULL",
        "contacts": "SELECT COUNT(*) FROM contacts WHERE unified_contact_id IS NULL",
        "inbox_contacts": "SELECT COUNT(*) FROM inbox_contacts WHERE unified_contact_id IS NULL",
        "opportunities": """
            SELECT COUNT(*) FROM opportunities
            WHERE unified_contact_id IS NULL
            AND (customer_id IS NOT NULL OR lead_id IS NOT NULL)
        """,
        "activities": """
            SELECT COUNT(*) FROM activities
            WHERE unified_contact_id IS NULL
            AND (customer_id IS NOT NULL OR lead_id IS NOT NULL OR contact_id IS NOT NULL)
        """,
        "omni_conversations": """
            SELECT COUNT(*) FROM omni_conversations
            WHERE unified_contact_id IS NULL
            AND (customer_id IS NOT NULL OR lead_id IS NOT NULL OR contact_email IS NOT NULL)
        """,
        "omni_participants": """
            SELECT COUNT(*) FROM omni_participants
            WHERE unified_contact_id IS NULL
            AND customer_id IS NOT NULL
        """,
    }

    results = {}
    for table, query in queries.items():
        count = session.execute(text(query)).scalar()
        results[table] = count
    return results


def print_status(counts: dict[str, int]) -> None:
    """Print orphan status in a nice format."""
    print("\n" + "=" * 60)
    print("UNIFIED CONTACT BACKFILL STATUS")
    print("=" * 60)

    total = sum(counts.values())
    all_ready = total == 0

    for table, count in counts.items():
        status = "OK" if count == 0 else f"{count:,} orphaned"
        symbol = "[OK]" if count == 0 else "[!!]"
        print(f"  {symbol} {table}: {status}")

    print("-" * 60)
    if all_ready:
        print("  STATUS: Ready for NOT NULL enforcement migration")
        print("  Run: alembic upgrade uc003_enforce_not_null")
    else:
        print(f"  STATUS: {total:,} records need backfill")
        print("  Run: python scripts/backfill_unified_contacts.py")
    print("=" * 60 + "\n")

    return all_ready


def main():
    parser = argparse.ArgumentParser(
        description="Backfill unified_contact_id for all contact-related records"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Only show current status, don't make changes"
    )
    args = parser.parse_args()

    # Create database session
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get current status
        counts = get_orphan_counts(session)
        is_ready = print_status(counts)

        if args.status:
            sys.exit(0 if is_ready else 1)

        if is_ready:
            print("No backfill needed - all records have unified_contact_id")
            sys.exit(0)

        if args.dry_run:
            print("\n[DRY RUN] Would update the following records:")
            print(f"  - {counts['customers']:,} customers")
            print(f"  - {counts['contacts']:,} CRM contacts")
            print(f"  - {counts['inbox_contacts']:,} inbox contacts")
            print("\nRun without --dry-run to perform the backfill.")
            sys.exit(0)

        # Perform backfill
        print("\nStarting backfill...")
        enforcement = UnifiedContactEnforcement(session)
        results = enforcement.backfill_missing_unified_contacts()

        print("\nBackfill complete:")
        print(f"  - Customers updated: {results['customers_updated']:,}")
        print(f"  - CRM contacts updated: {results['contacts_updated']:,}")
        print(f"  - Inbox contacts updated: {results['inbox_contacts_updated']:,}")

        # Link remaining tables (opportunities, activities, etc.)
        print("\nLinking related tables...")

        session.execute(text("""
            UPDATE opportunities o
            SET unified_contact_id = COALESCE(
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_customer_id = o.customer_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_lead_id = o.lead_id LIMIT 1)
            )
            WHERE o.unified_contact_id IS NULL
        """))

        session.execute(text("""
            UPDATE activities a
            SET unified_contact_id = COALESCE(
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_customer_id = a.customer_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_lead_id = a.lead_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_contact_id = a.contact_id LIMIT 1)
            )
            WHERE a.unified_contact_id IS NULL
        """))

        session.execute(text("""
            UPDATE omni_conversations oc
            SET unified_contact_id = COALESCE(
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_customer_id = oc.customer_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_lead_id = oc.lead_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.email = oc.contact_email AND oc.contact_email IS NOT NULL LIMIT 1)
            )
            WHERE oc.unified_contact_id IS NULL
        """))

        session.execute(text("""
            UPDATE omni_participants op
            SET unified_contact_id = COALESCE(
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_customer_id = op.customer_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.email = op.handle AND op.channel_type = 'email' LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.phone = op.handle AND op.channel_type IN ('sms', 'whatsapp') LIMIT 1)
            )
            WHERE op.unified_contact_id IS NULL
        """))

        session.commit()
        print("Related tables linked.")

        # Final status
        final_counts = get_orphan_counts(session)
        print_status(final_counts)

    except Exception as e:
        session.rollback()
        print(f"\nERROR: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
