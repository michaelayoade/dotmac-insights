#!/usr/bin/env python3
"""
Backfill Splynx partner/reseller parties and account links.

Usage:
  python scripts/backfill_splynx_partners.py --status
  python scripts/backfill_splynx_partners.py --dry-run
  python scripts/backfill_splynx_partners.py
"""
import argparse
import json
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


def _parse_partners_ids(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        decoded = json.loads(raw)
        if isinstance(decoded, list):
            return [str(item) for item in decoded if str(item).strip()]
        if isinstance(decoded, (str, int)):
            return [str(decoded)]
    except json.JSONDecodeError:
        cleaned = raw.strip().strip("[]")
        if not cleaned:
            return []
        parts = [p.strip().strip('"').strip("'") for p in cleaned.split(",")]
        return [p for p in parts if p]
    return []


def _collect_partner_ids(session) -> set[str]:
    partner_ids = set()

    for row in session.execute(
        text(
            "SELECT DISTINCT custom_fields->>'partner_id' AS partner_id "
            "FROM parties "
            "WHERE custom_fields ? 'partner_id' "
            "AND custom_fields->>'partner_id' IS NOT NULL "
            "AND custom_fields->>'partner_id' != ''"
        )
    ).mappings():
        partner_ids.add(str(row["partner_id"]))

    for row in session.execute(
        text("SELECT DISTINCT partner_id FROM leads WHERE partner_id IS NOT NULL")
    ).mappings():
        partner_ids.add(str(row["partner_id"]))

    for row in session.execute(
        text("SELECT DISTINCT partner_id FROM administrators WHERE partner_id IS NOT NULL")
    ).mappings():
        partner_ids.add(str(row["partner_id"]))

    for row in session.execute(
        text("SELECT partners_ids FROM routers WHERE partners_ids IS NOT NULL")
    ).mappings():
        for partner_id in _parse_partners_ids(row["partners_ids"]):
            partner_ids.add(str(partner_id))

    return {pid for pid in partner_ids if pid and pid != "0"}


def _get_existing_partner_map(session) -> dict[str, int]:
    rows = session.execute(
        text(
            "SELECT external_id, party_id "
            "FROM party_external_ids "
            "WHERE system = 'splynx_partner'"
        )
    ).mappings()
    return {str(r["external_id"]): r["party_id"] for r in rows}


def _ensure_partner_party(session, partner_id: str) -> int:
    existing_party_id = session.execute(
        text(
            "SELECT party_id FROM party_external_ids "
            "WHERE system = 'splynx_partner' AND external_id = :external_id"
        ),
        {"external_id": partner_id},
    ).scalar()
    if existing_party_id:
        return existing_party_id

    party_id = session.execute(
        text(
            "INSERT INTO parties (type, name) "
            "VALUES ('organization', :name) "
            "RETURNING id"
        ),
        {"name": f"Splynx Partner {partner_id}"},
    ).scalar_one()

    session.execute(
        text(
            "INSERT INTO party_external_ids "
            "(party_id, system, external_id, external_key_type, is_primary) "
            "VALUES (:party_id, 'splynx_partner', :external_id, 'partner_id', true)"
        ),
        {"party_id": party_id, "external_id": partner_id},
    )

    role_exists = session.execute(
        text(
            "SELECT id FROM party_roles "
            "WHERE party_id = :party_id AND role = 'reseller' AND until IS NULL"
        ),
        {"party_id": party_id},
    ).scalar()
    if not role_exists:
        session.execute(
            text(
                "INSERT INTO party_roles (party_id, role) "
                "VALUES (:party_id, 'reseller')"
            ),
            {"party_id": party_id},
        )

    return party_id


def _count_missing_reseller_links(session) -> int:
    return session.execute(
        text(
            "SELECT COUNT(*) "
            "FROM customer_accounts ca "
            "JOIN parties p ON p.id = ca.party_id "
            "LEFT JOIN customer_account_resellers car "
            "  ON car.account_id = ca.id AND car.until IS NULL "
            "WHERE p.custom_fields ? 'partner_id' "
            "AND p.custom_fields->>'partner_id' IS NOT NULL "
            "AND p.custom_fields->>'partner_id' != '' "
            "AND car.id IS NULL"
        )
    ).scalar()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Splynx partner/reseller data")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without writing")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    args = parser.parse_args()

    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        partner_ids = _collect_partner_ids(session)
        existing_map = _get_existing_partner_map(session)
        missing_partner_ids = [pid for pid in partner_ids if pid not in existing_map]
        missing_links = _count_missing_reseller_links(session)

        print("Splynx partner/reseller backfill status:")
        print(f"  partner_ids_detected: {len(partner_ids)}")
        print(f"  partner_parties_existing: {len(existing_map)}")
        print(f"  partner_parties_missing: {len(missing_partner_ids)}")
        print(f"  customer_accounts_missing_reseller_link: {missing_links}")

        if args.status:
            return

        if args.dry_run:
            print("\n[DRY RUN] Would create partner parties for:")
            for pid in sorted(missing_partner_ids)[:25]:
                print(f"  - {pid}")
            if len(missing_partner_ids) > 25:
                print(f"  ... and {len(missing_partner_ids) - 25} more")
            print(f"\n[DRY RUN] Would link {missing_links} customer accounts to resellers.")
            return

        partner_map = dict(existing_map)
        for partner_id in sorted(missing_partner_ids):
            partner_map[partner_id] = _ensure_partner_party(session, partner_id)

        rows = session.execute(
            text(
                "SELECT ca.id AS account_id, p.custom_fields->>'partner_id' AS partner_id "
                "FROM customer_accounts ca "
                "JOIN parties p ON p.id = ca.party_id "
                "WHERE p.custom_fields ? 'partner_id' "
                "AND p.custom_fields->>'partner_id' IS NOT NULL "
                "AND p.custom_fields->>'partner_id' != ''"
            )
        ).mappings()

        linked = 0
        for row in rows:
            partner_id = str(row["partner_id"])
            reseller_party_id = partner_map.get(partner_id)
            if not reseller_party_id:
                reseller_party_id = _ensure_partner_party(session, partner_id)
                partner_map[partner_id] = reseller_party_id

            existing_link = session.execute(
                text(
                    "SELECT id FROM customer_account_resellers "
                    "WHERE account_id = :account_id "
                    "AND reseller_party_id = :reseller_party_id "
                    "AND until IS NULL"
                ),
                {
                    "account_id": row["account_id"],
                    "reseller_party_id": reseller_party_id,
                },
            ).scalar()
            if not existing_link:
                session.execute(
                    text(
                        "INSERT INTO customer_account_resellers (account_id, reseller_party_id) "
                        "VALUES (:account_id, :reseller_party_id)"
                    ),
                    {
                        "account_id": row["account_id"],
                        "reseller_party_id": reseller_party_id,
                    },
                )
                linked += 1

        session.commit()
        print(f"\nBackfill complete. Customer accounts linked: {linked}")

    except Exception as exc:
        session.rollback()
        print(f"ERROR: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
