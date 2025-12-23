#!/usr/bin/env python3
"""
Push Cleaned Addresses to Splynx

This script pushes the normalized city and state values from our database
back to Splynx to keep the source system clean.

Usage:
    # Dry run (preview changes)
    python scripts/push_addresses_to_splynx.py --dry-run

    # Push changes
    python scripts/push_addresses_to_splynx.py

    # Limit records (for testing)
    python scripts/push_addresses_to_splynx.py --limit 10
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import structlog
from sqlalchemy import and_

from app.database import SessionLocal
from app.models.customer import Customer
from app.config import settings

logger = structlog.get_logger()


class SplynxUpdater:
    """Simple client for updating Splynx customer records."""

    def __init__(self):
        self.base_url = settings.splynx_api_url.rstrip("/")
        self.auth_basic = settings.splynx_auth_basic

        if not self.auth_basic:
            raise ValueError("SPLYNX_AUTH_BASIC not configured")

    def _get_headers(self):
        return {
            "Authorization": f"Basic {self.auth_basic}",
            "Content-Type": "application/json",
        }

    async def update_customer(self, client: httpx.AsyncClient, splynx_id: int, data: dict) -> dict:
        """Update a customer in Splynx."""
        url = f"{self.base_url}/admin/customers/customer/{splynx_id}"

        response = await client.put(
            url,
            headers=self._get_headers(),
            json=data,
            timeout=30,
        )

        # Splynx returns 202 Accepted for successful updates
        if response.status_code in (200, 202):
            return {"success": True, "data": response.json() if response.text and response.text != "null" else None}
        else:
            return {
                "success": False,
                "status": response.status_code,
                "error": response.text[:500] if response.text else "Unknown error",
            }

    async def get_customer(self, client: httpx.AsyncClient, splynx_id: int) -> dict:
        """Get current customer data from Splynx."""
        url = f"{self.base_url}/admin/customers/customer/{splynx_id}"

        response = await client.get(
            url,
            headers=self._get_headers(),
            timeout=30,
        )

        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "status": response.status_code}


async def get_customers_to_update(db, limit=None):
    """Get customers that have normalized city/state values to push."""
    query = db.query(Customer).filter(
        and_(
            Customer.splynx_id.isnot(None),
            # Only include records where we have city or state to update
            (Customer.city.isnot(None)) | (Customer.state.isnot(None))
        )
    )

    if limit:
        query = query.limit(limit)

    return query.all()


async def preview_updates(db, limit=None):
    """Preview what updates would be made."""
    customers = await get_customers_to_update(db, limit)

    print(f"\nFound {len(customers)} customers with addresses to push to Splynx\n")

    # Show sample
    print("Sample of updates (first 20):")
    print("-" * 80)
    for customer in customers[:20]:
        print(f"  [{customer.splynx_id}] {customer.name}")
        print(f"      city: {customer.city}, state: {customer.state}")

    # Stats
    with_city = sum(1 for c in customers if c.city)
    with_state = sum(1 for c in customers if c.state)
    print(f"\nStats:")
    print(f"  With city:  {with_city}")
    print(f"  With state: {with_state}")

    return len(customers)


async def push_updates(db, updater: SplynxUpdater, limit=None, batch_size=10):
    """Push address updates to Splynx."""
    customers = await get_customers_to_update(db, limit)
    total = len(customers)

    print(f"\nPushing updates for {total} customers...")

    stats = {
        "success": 0,
        "failed": 0,
        "skipped": 0,
    }
    errors = []

    async with httpx.AsyncClient() as client:
        for i, customer in enumerate(customers, 1):
            # Build update payload - only city is writable via Splynx API
            # (region/state and country fields are read-only)
            if not customer.city:
                stats["skipped"] += 1
                continue

            update_data = {"city": customer.city}

            try:
                result = await updater.update_customer(client, customer.splynx_id, update_data)

                if result["success"]:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
                    errors.append({
                        "splynx_id": customer.splynx_id,
                        "name": customer.name,
                        "error": result.get("error", "Unknown"),
                        "status": result.get("status"),
                    })

            except Exception as e:
                stats["failed"] += 1
                errors.append({
                    "splynx_id": customer.splynx_id,
                    "name": customer.name,
                    "error": str(e),
                })

            # Progress
            if i % 100 == 0:
                print(f"  Progress: {i}/{total} ({100*i/total:.1f}%) - Success: {stats['success']}, Failed: {stats['failed']}")

            # Small delay to avoid overwhelming the API
            if i % batch_size == 0:
                await asyncio.sleep(0.5)

    return stats, errors


async def main():
    parser = argparse.ArgumentParser(
        description="Push cleaned addresses to Splynx",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without pushing them"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of records to process"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.dry_run:
            print("=" * 70)
            print("DRY RUN - PREVIEW OF UPDATES")
            print("=" * 70)

            count = await preview_updates(db, args.limit)

            print("\n" + "=" * 70)
            print(f"To push these {count} updates to Splynx, run without --dry-run")
            print("=" * 70)

        else:
            print("=" * 70)
            print("PUSHING ADDRESSES TO SPLYNX")
            print("=" * 70)

            if not args.yes:
                confirm = input("\nThis will update customer records in Splynx. Continue? [y/N]: ")
                if confirm.lower() != "y":
                    print("Aborted.")
                    return

            updater = SplynxUpdater()
            stats, errors = await push_updates(db, updater, args.limit)

            print("\n" + "=" * 70)
            print("COMPLETED")
            print("=" * 70)
            print(f"  Success: {stats['success']}")
            print(f"  Failed:  {stats['failed']}")
            print(f"  Skipped: {stats['skipped']}")

            if errors:
                print(f"\nFirst 10 errors:")
                for err in errors[:10]:
                    print(f"  [{err['splynx_id']}] {err['name']}: {err['error']}")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
