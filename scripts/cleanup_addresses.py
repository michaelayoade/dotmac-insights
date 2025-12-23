#!/usr/bin/env python3
"""
Address Data Cleanup Script

This script normalizes customer address data (city, state) and fixes common
data quality issues like:
- Inconsistent FCT/Abuja variations (30+ different formats)
- Missing state values
- Numeric IDs in city field
- GPS coordinates in city field
- Whitespace and punctuation issues

Usage:
    # Dry run (preview changes)
    python scripts/cleanup_addresses.py --dry-run

    # Apply changes
    python scripts/cleanup_addresses.py

    # Verbose output
    python scripts/cleanup_addresses.py --verbose
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from collections import Counter
from sqlalchemy import func
from app.database import SessionLocal
from app.models.customer import Customer
from app.utils.address_normalizer import normalize_address


def analyze_current_state(db):
    """Analyze current address data quality."""
    total = db.query(func.count(Customer.id)).scalar()

    # City stats
    null_cities = db.query(func.count(Customer.id)).filter(Customer.city.is_(None)).scalar()
    distinct_cities = db.query(func.count(func.distinct(Customer.city))).scalar()

    # State stats
    null_states = db.query(func.count(Customer.id)).filter(Customer.state.is_(None)).scalar()

    print("=" * 70)
    print("CURRENT DATA QUALITY")
    print("=" * 70)
    print(f"Total customers:        {total:,}")
    print(f"Null/empty cities:      {null_cities:,} ({100*null_cities/total:.1f}%)")
    print(f"Distinct city values:   {distinct_cities:,}")
    print(f"Null/empty states:      {null_states:,} ({100*null_states/total:.1f}%)")
    print()

    return total


def preview_changes(db, limit=None):
    """Preview what changes would be made."""
    query = db.query(Customer)
    if limit:
        query = query.limit(limit)

    customers = query.all()

    changes = {
        "city_normalized": 0,
        "state_inferred": 0,
        "state_normalized": 0,
        "city_cleared_invalid": 0,
        "gps_extracted": 0,
        "no_change": 0,
    }

    city_before_after = Counter()
    state_inferred_from = Counter()

    for customer in customers:
        result = normalize_address(
            customer.city,
            customer.state,
            customer.latitude,
            customer.longitude
        )

        new_city = result["city"]
        new_state = result["state"]
        was_invalid = result["was_invalid"]

        changed = False

        # Check city changes
        if customer.city != new_city:
            if was_invalid:
                changes["city_cleared_invalid"] += 1
            elif new_city:
                changes["city_normalized"] += 1
                city_before_after[(customer.city, new_city)] += 1
            changed = True

        # Check state changes
        if customer.state != new_state:
            if new_state:
                if customer.state:
                    changes["state_normalized"] += 1
                else:
                    changes["state_inferred"] += 1
                    state_inferred_from[customer.city] += 1
            changed = True

        # Check GPS extraction
        if result["latitude"] and not customer.latitude:
            changes["gps_extracted"] += 1
            changed = True

        if not changed:
            changes["no_change"] += 1

    return changes, city_before_after, state_inferred_from


def apply_changes(db, verbose=False, batch_size=500):
    """Apply address normalization to all customers."""
    customers = db.query(Customer).all()
    total = len(customers)

    stats = {
        "city_changed": 0,
        "state_changed": 0,
        "gps_extracted": 0,
        "processed": 0,
    }

    for i, customer in enumerate(customers, 1):
        result = normalize_address(
            customer.city,
            customer.state,
            customer.latitude,
            customer.longitude
        )

        changes_made = []

        # Update city
        if customer.city != result["city"]:
            if verbose:
                changes_made.append(f"city: '{customer.city}' -> '{result['city']}'")
            customer.city = result["city"]
            stats["city_changed"] += 1

        # Update state
        if customer.state != result["state"]:
            if verbose:
                changes_made.append(f"state: '{customer.state}' -> '{result['state']}'")
            customer.state = result["state"]
            stats["state_changed"] += 1

        # Extract GPS if available
        if result["latitude"] and not customer.latitude:
            if verbose:
                changes_made.append(f"gps extracted: ({result['latitude']}, {result['longitude']})")
            customer.latitude = result["latitude"]
            customer.longitude = result["longitude"]
            stats["gps_extracted"] += 1

        if verbose and changes_made:
            print(f"  [{customer.id}] {customer.name}: {', '.join(changes_made)}")

        stats["processed"] += 1

        # Commit in batches
        if i % batch_size == 0:
            db.commit()
            print(f"  Progress: {i:,}/{total:,} ({100*i/total:.1f}%)")

    # Final commit
    db.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Normalize customer address data (city, state)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output for each change"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of records to process (for testing)"
    )

    args = parser.parse_args()

    db = SessionLocal()

    try:
        # Show current state
        total = analyze_current_state(db)

        if args.dry_run:
            print("=" * 70)
            print("DRY RUN - PREVIEW OF CHANGES")
            print("=" * 70)

            changes, city_changes, state_inferred = preview_changes(db, args.limit)

            print(f"\nSummary of changes that would be made:")
            print(f"  Cities normalized:       {changes['city_normalized']:,}")
            print(f"  Cities cleared (invalid): {changes['city_cleared_invalid']:,}")
            print(f"  States inferred:         {changes['state_inferred']:,}")
            print(f"  States normalized:       {changes['state_normalized']:,}")
            print(f"  GPS coordinates extracted: {changes['gps_extracted']:,}")
            print(f"  No change needed:        {changes['no_change']:,}")

            if city_changes:
                print(f"\nTop 20 city normalizations:")
                for (before, after), count in city_changes.most_common(20):
                    print(f"  {count:4d}x  '{before}' -> '{after}'")

            if state_inferred:
                print(f"\nTop 20 states inferred from cities:")
                for city, count in state_inferred.most_common(20):
                    print(f"  {count:4d}x  from '{city}'")

            print("\n" + "=" * 70)
            print("To apply these changes, run without --dry-run")
            print("=" * 70)

        else:
            print("=" * 70)
            print("APPLYING CHANGES")
            print("=" * 70)

            confirm = input("\nThis will modify customer records. Continue? [y/N]: ")
            if confirm.lower() != "y":
                print("Aborted.")
                return

            print("\nApplying changes...")
            stats = apply_changes(db, verbose=args.verbose)

            print("\n" + "=" * 70)
            print("COMPLETED")
            print("=" * 70)
            print(f"  Records processed:  {stats['processed']:,}")
            print(f"  Cities changed:     {stats['city_changed']:,}")
            print(f"  States changed:     {stats['state_changed']:,}")
            print(f"  GPS extracted:      {stats['gps_extracted']:,}")

            # Show new state
            print("\n")
            analyze_current_state(db)

    finally:
        db.close()


if __name__ == "__main__":
    main()
