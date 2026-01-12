#!/usr/bin/env python3
"""
Backfill gl_entries.account_id from accounts.erpnext_id.

Usage:
  python scripts/backfill_gl_entries_account_id.py --status
  python scripts/backfill_gl_entries_account_id.py --dry-run
  python scripts/backfill_gl_entries_account_id.py
"""
import argparse
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


def _counts(session) -> dict:
    total = session.execute(text("SELECT COUNT(*) FROM gl_entries")).scalar() or 0
    missing = session.execute(
        text("SELECT COUNT(*) FROM gl_entries WHERE account_id IS NULL")
    ).scalar() or 0
    matched = session.execute(
        text(
            "SELECT COUNT(*) "
            "FROM gl_entries ge "
            "JOIN accounts a ON a.erpnext_id = ge.account"
        )
    ).scalar() or 0
    return {"total": total, "missing_account_id": missing, "matchable": matched}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill gl_entries.account_id from accounts.erpnext_id"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show actions without writing")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    args = parser.parse_args()

    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        counts = _counts(session)
        print("GL entry account_id backfill status:")
        print(f"  total_gl_entries: {counts['total']}")
        print(f"  missing_account_id: {counts['missing_account_id']}")
        print(f"  matchable_by_erpnext_id: {counts['matchable']}")

        if args.status:
            return

        if args.dry_run:
            print("\n[DRY RUN] Would backfill account_id for matchable entries.")
            return

        session.execute(
            text(
                "UPDATE gl_entries ge "
                "SET account_id = a.id "
                "FROM accounts a "
                "WHERE ge.account_id IS NULL "
                "AND a.erpnext_id = ge.account"
            )
        )
        session.commit()

        counts = _counts(session)
        print("\nBackfill complete.")
        print(f"  missing_account_id: {counts['missing_account_id']}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
