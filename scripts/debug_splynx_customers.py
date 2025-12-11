#!/usr/bin/env python3
"""
Debug script to capture raw Splynx customer data and analyze status values.

Usage:
    python scripts/debug_splynx_customers.py
"""

import asyncio
import json
import sys
from collections import Counter

sys.path.insert(0, ".")

import httpx
from app.config import settings


async def fetch_customers_raw():
    """Fetch raw customer data from Splynx API."""
    base_url = settings.splynx_api_url.rstrip("/")
    auth_basic = settings.splynx_auth_basic

    if not base_url:
        print("ERROR: SPLYNX_API_URL not configured")
        return

    if not auth_basic:
        print("ERROR: SPLYNX_AUTH_BASIC not configured")
        return

    headers = {
        "Authorization": f"Basic {auth_basic}",
        "Content-Type": "application/json",
    }

    print(f"Connecting to: {base_url}")
    print(f"Endpoint: /admin/customers/customer")
    print("-" * 60)

    async with httpx.AsyncClient(timeout=60) as client:
        # Fetch first page of customers
        response = await client.get(
            f"{base_url}/admin/customers/customer",
            headers=headers,
            params={"page": 0, "per_page": 50}  # Get 50 customers as sample
        )

        if response.status_code != 200:
            print(f"ERROR: API returned {response.status_code}")
            print(response.text[:500])
            return

        customers = response.json()

        print(f"Fetched {len(customers)} customers\n")

        # Analyze status values
        print("=" * 60)
        print("STATUS ANALYSIS")
        print("=" * 60)

        statuses = [c.get("status") for c in customers]
        status_counts = Counter(statuses)

        print(f"\nUnique status values found:")
        for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
            print(f"  '{status}': {count} customers")

        # Show sample records with each status
        print("\n" + "=" * 60)
        print("SAMPLE RECORDS BY STATUS")
        print("=" * 60)

        seen_statuses = set()
        for cust in customers:
            status = cust.get("status")
            if status not in seen_statuses:
                seen_statuses.add(status)
                print(f"\n--- Status: '{status}' ---")
                print(f"  id: {cust.get('id')}")
                print(f"  name: {cust.get('name')}")
                print(f"  login: {cust.get('login')}")
                print(f"  status: {cust.get('status')}")
                print(f"  category: {cust.get('category')}")
                print(f"  billing_type: {cust.get('billing_type')}")

        # Show all fields from first customer
        print("\n" + "=" * 60)
        print("FULL RECORD SAMPLE (first customer)")
        print("=" * 60)
        if customers:
            print(json.dumps(customers[0], indent=2, default=str))

        # Save full response to file for inspection
        with open("scripts/splynx_customers_sample.json", "w") as f:
            json.dump(customers, f, indent=2, default=str)
        print(f"\nFull sample saved to: scripts/splynx_customers_sample.json")


if __name__ == "__main__":
    asyncio.run(fetch_customers_raw())
