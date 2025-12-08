#!/usr/bin/env python3
"""
Dotmac Insights CLI - Command line tool for managing the data sync platform.

Usage:
    python cli.py sync all          # Sync all data sources
    python cli.py sync splynx       # Sync Splynx only
    python cli.py sync erpnext      # Sync ERPNext only
    python cli.py sync chatwoot     # Sync Chatwoot only
    python cli.py test-connections  # Test all API connections
    python cli.py stats             # Show data statistics
    python cli.py init-db           # Initialize database tables
"""

import asyncio
import argparse
import sys
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, ".")

from app.database import engine, Base, SessionLocal
from app.sync.splynx import SplynxSync
from app.sync.erpnext import ERPNextSync
from app.sync.chatwoot import ChatwootSync
from app.models import *


def init_db():
    """Initialize database tables."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


async def test_connections():
    """Test connections to all external systems."""
    db = SessionLocal()

    print("\nTesting connections...\n")

    # Splynx
    print("Splynx: ", end="")
    splynx = SplynxSync(db)
    if await splynx.test_connection():
        print("✓ Connected")
    else:
        print("✗ Failed")

    # ERPNext
    print("ERPNext: ", end="")
    erpnext = ERPNextSync(db)
    if await erpnext.test_connection():
        print("✓ Connected")
    else:
        print("✗ Failed")

    # Chatwoot
    print("Chatwoot: ", end="")
    chatwoot = ChatwootSync(db)
    if await chatwoot.test_connection():
        print("✓ Connected")
    else:
        print("✗ Failed")

    db.close()
    print()


async def sync_source(source: str, full_sync: bool = False):
    """Sync a specific data source."""
    db = SessionLocal()

    sync_type = "full" if full_sync else "incremental"
    print(f"\nStarting {sync_type} sync for {source}...\n")

    try:
        if source == "splynx":
            client = SplynxSync(db)
        elif source == "erpnext":
            client = ERPNextSync(db)
        elif source == "chatwoot":
            client = ChatwootSync(db)
        else:
            print(f"Unknown source: {source}")
            return

        await client.sync_all(full_sync=full_sync)
        print(f"\n{source} sync completed successfully!")

    except Exception as e:
        print(f"\nSync failed: {e}")

    finally:
        db.close()


async def sync_all(full_sync: bool = False):
    """Sync all data sources."""
    print("\n" + "=" * 50)
    print("DOTMAC INSIGHTS - FULL DATA SYNC")
    print("=" * 50)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Sync type: {'Full' if full_sync else 'Incremental'}")
    print("=" * 50)

    sources = ["splynx", "erpnext", "chatwoot"]

    for source in sources:
        print(f"\n--- Syncing {source.upper()} ---")
        await sync_source(source, full_sync)

    print("\n" + "=" * 50)
    print("ALL SYNCS COMPLETED")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50 + "\n")


def show_stats():
    """Show data statistics."""
    db = SessionLocal()

    print("\n" + "=" * 50)
    print("DOTMAC INSIGHTS - DATA STATISTICS")
    print("=" * 50)

    # Customers
    total_customers = db.query(Customer).count()
    active_customers = db.query(Customer).filter(Customer.status == CustomerStatus.ACTIVE).count()
    print(f"\nCustomers: {total_customers} total, {active_customers} active")

    # POPs
    pop_count = db.query(Pop).count()
    print(f"POPs: {pop_count}")

    # Subscriptions
    sub_count = db.query(Subscription).count()
    active_subs = db.query(Subscription).filter(Subscription.status == SubscriptionStatus.ACTIVE).count()
    print(f"Subscriptions: {sub_count} total, {active_subs} active")

    # Invoices
    invoice_count = db.query(Invoice).count()
    print(f"Invoices: {invoice_count}")

    # Payments
    payment_count = db.query(Payment).count()
    print(f"Payments: {payment_count}")

    # Conversations
    conv_count = db.query(Conversation).count()
    print(f"Conversations: {conv_count}")

    # Messages
    msg_count = db.query(Message).count()
    print(f"Messages: {msg_count}")

    # Employees
    emp_count = db.query(Employee).count()
    print(f"Employees: {emp_count}")

    # Expenses
    exp_count = db.query(Expense).count()
    print(f"Expenses: {exp_count}")

    # Sync logs
    sync_count = db.query(SyncLog).count()
    last_sync = db.query(SyncLog).order_by(SyncLog.started_at.desc()).first()
    print(f"\nSync logs: {sync_count}")
    if last_sync:
        print(f"Last sync: {last_sync.source.value} - {last_sync.entity_type} at {last_sync.started_at}")

    print("\n" + "=" * 50 + "\n")

    db.close()


def main():
    parser = argparse.ArgumentParser(description="Dotmac Insights CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync data from external sources")
    sync_parser.add_argument("source", choices=["all", "splynx", "erpnext", "chatwoot"], help="Source to sync")
    sync_parser.add_argument("--full", action="store_true", help="Perform full sync instead of incremental")

    # Test connections command
    subparsers.add_parser("test-connections", help="Test connections to all external systems")

    # Stats command
    subparsers.add_parser("stats", help="Show data statistics")

    # Init DB command
    subparsers.add_parser("init-db", help="Initialize database tables")

    args = parser.parse_args()

    if args.command == "sync":
        if args.source == "all":
            asyncio.run(sync_all(args.full))
        else:
            asyncio.run(sync_source(args.source, args.full))

    elif args.command == "test-connections":
        asyncio.run(test_connections())

    elif args.command == "stats":
        show_stats()

    elif args.command == "init-db":
        init_db()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
