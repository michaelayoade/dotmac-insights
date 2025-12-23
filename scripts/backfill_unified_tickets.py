#!/usr/bin/env python3
"""
Backfill script for UnifiedTicket

Migrates existing tickets and conversations into the unified_tickets table.
Links to unified_contacts where possible via existing customer/contact relationships.

Usage:
    # Check current status
    python scripts/backfill_unified_tickets.py --status

    # Dry run - show what would be migrated
    python scripts/backfill_unified_tickets.py --dry-run

    # Actually perform the backfill (default batch size 500)
    python scripts/backfill_unified_tickets.py

    # Custom batch size
    python scripts/backfill_unified_tickets.py --batch-size 1000

    # Verbose output
    python scripts/backfill_unified_tickets.py --verbose
"""
import argparse
import sys
import os
from datetime import datetime
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, func, select, and_, or_
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings


# =============================================================================
# STATUS QUERIES
# =============================================================================

def get_source_counts(session: Session) -> dict:
    """Get counts of source records (tickets, conversations)."""
    return {
        "tickets_total": session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE is_deleted = false")
        ).scalar() or 0,
        "tickets_splynx": session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE splynx_id IS NOT NULL AND is_deleted = false")
        ).scalar() or 0,
        "tickets_erpnext": session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE erpnext_id IS NOT NULL AND is_deleted = false")
        ).scalar() or 0,
        "conversations_total": session.execute(
            text("SELECT COUNT(*) FROM conversations")
        ).scalar() or 0,
        "conversations_chatwoot": session.execute(
            text("SELECT COUNT(*) FROM conversations WHERE chatwoot_id IS NOT NULL")
        ).scalar() or 0,
        "omni_conversations_total": session.execute(
            text("SELECT COUNT(*) FROM omni_conversations")
        ).scalar() or 0,
    }


def get_unified_counts(session: Session) -> dict:
    """Get counts of unified tickets by source."""
    return {
        "unified_total": session.execute(
            text("SELECT COUNT(*) FROM unified_tickets WHERE is_deleted = false")
        ).scalar() or 0,
        "unified_from_tickets": session.execute(
            text("SELECT COUNT(*) FROM unified_tickets WHERE legacy_ticket_id IS NOT NULL")
        ).scalar() or 0,
        "unified_from_conversations": session.execute(
            text("SELECT COUNT(*) FROM unified_tickets WHERE legacy_conversation_id IS NOT NULL")
        ).scalar() or 0,
        "unified_from_omni": session.execute(
            text("SELECT COUNT(*) FROM unified_tickets WHERE legacy_omni_conversation_id IS NOT NULL")
        ).scalar() or 0,
        "unified_with_contact": session.execute(
            text("SELECT COUNT(*) FROM unified_tickets WHERE unified_contact_id IS NOT NULL")
        ).scalar() or 0,
    }


def get_unmigrated_counts(session: Session) -> dict:
    """Get counts of records not yet migrated to unified_tickets."""
    return {
        "tickets_unmigrated": session.execute(text("""
            SELECT COUNT(*) FROM tickets t
            WHERE t.is_deleted = false
            AND NOT EXISTS (
                SELECT 1 FROM unified_tickets ut
                WHERE ut.legacy_ticket_id = t.id
            )
        """)).scalar() or 0,
        "conversations_unmigrated": session.execute(text("""
            SELECT COUNT(*) FROM conversations c
            WHERE NOT EXISTS (
                SELECT 1 FROM unified_tickets ut
                WHERE ut.legacy_conversation_id = c.id
            )
        """)).scalar() or 0,
        "omni_conversations_unmigrated": session.execute(text("""
            SELECT COUNT(*) FROM omni_conversations oc
            WHERE NOT EXISTS (
                SELECT 1 FROM unified_tickets ut
                WHERE ut.legacy_omni_conversation_id = oc.id
            )
        """)).scalar() or 0,
    }


def print_status(source_counts: dict, unified_counts: dict, unmigrated_counts: dict) -> bool:
    """Print migration status in a nice format."""
    print("\n" + "=" * 70)
    print("UNIFIED TICKET BACKFILL STATUS")
    print("=" * 70)

    print("\nSOURCE RECORDS:")
    print(f"  Tickets (total):           {source_counts['tickets_total']:,}")
    print(f"    - From Splynx:           {source_counts['tickets_splynx']:,}")
    print(f"    - From ERPNext:          {source_counts['tickets_erpnext']:,}")
    print(f"  Conversations (Chatwoot):  {source_counts['conversations_total']:,}")
    print(f"  OmniConversations:         {source_counts['omni_conversations_total']:,}")

    print("\nUNIFIED TICKETS:")
    print(f"  Total unified:             {unified_counts['unified_total']:,}")
    print(f"    - From tickets:          {unified_counts['unified_from_tickets']:,}")
    print(f"    - From conversations:    {unified_counts['unified_from_conversations']:,}")
    print(f"    - From omni:             {unified_counts['unified_from_omni']:,}")
    print(f"  With unified_contact:      {unified_counts['unified_with_contact']:,}")

    total_unmigrated = sum(unmigrated_counts.values())
    print("\nUNMIGRATED (need backfill):")
    print(f"  [{'OK' if unmigrated_counts['tickets_unmigrated'] == 0 else '!!'}] Tickets:              {unmigrated_counts['tickets_unmigrated']:,}")
    print(f"  [{'OK' if unmigrated_counts['conversations_unmigrated'] == 0 else '!!'}] Conversations:        {unmigrated_counts['conversations_unmigrated']:,}")
    print(f"  [{'OK' if unmigrated_counts['omni_conversations_unmigrated'] == 0 else '!!'}] OmniConversations:    {unmigrated_counts['omni_conversations_unmigrated']:,}")

    print("-" * 70)
    if total_unmigrated == 0:
        print("  STATUS: All records migrated to unified_tickets")
    else:
        print(f"  STATUS: {total_unmigrated:,} records need backfill")
        print("  Run: python scripts/backfill_unified_tickets.py")
    print("=" * 70 + "\n")

    return total_unmigrated == 0


# =============================================================================
# TICKET MIGRATION
# =============================================================================

def migrate_tickets(session: Session, batch_size: int, dry_run: bool, verbose: bool) -> dict:
    """
    Migrate tickets table to unified_tickets.

    Priority for linking:
    1. legacy_ticket_id (always set)
    2. splynx_id, erpnext_id (preserve from source)
    3. unified_contact_id via customer_id → customers.unified_contact_id
    """
    stats = {"created": 0, "skipped": 0, "linked_contact": 0, "errors": 0}

    # Get unmigrated tickets in batches
    offset = 0
    while True:
        tickets = session.execute(text("""
            SELECT
                t.id,
                t.ticket_number,
                t.subject,
                t.description,
                t.status,
                t.priority,
                t.ticket_type,
                t.issue_type,
                t.source,
                t.splynx_id,
                t.erpnext_id,
                t.customer_id,
                t.employee_id,
                t.assigned_employee_id,
                t.customer_email,
                t.customer_phone,
                t.customer_name,
                t.region,
                t.base_station,
                t.opening_date,
                t.resolution_date,
                t.response_by,
                t.resolution_by,
                t.first_responded_on,
                t.resolution,
                t.resolution_details,
                t.feedback_rating,
                t.feedback_text,
                t.tags,
                t.created_at,
                t.updated_at,
                c.unified_contact_id as customer_unified_contact_id
            FROM tickets t
            LEFT JOIN customers c ON t.customer_id = c.id
            WHERE t.is_deleted = false
            AND NOT EXISTS (
                SELECT 1 FROM unified_tickets ut WHERE ut.legacy_ticket_id = t.id
            )
            ORDER BY t.id
            LIMIT :limit OFFSET :offset
        """), {"limit": batch_size, "offset": offset}).fetchall()

        if not tickets:
            break

        for ticket in tickets:
            try:
                # Map status
                status_map = {
                    "open": "open",
                    "replied": "waiting",
                    "resolved": "resolved",
                    "closed": "closed",
                    "on_hold": "on_hold",
                }
                status = status_map.get(str(ticket.status).lower() if ticket.status else "open", "open")

                # Map priority
                priority_map = {
                    "low": "low",
                    "medium": "medium",
                    "high": "high",
                    "urgent": "urgent",
                }
                priority = priority_map.get(str(ticket.priority).lower() if ticket.priority else "medium", "medium")

                # Map source
                source_map = {
                    "erpnext": "erpnext",
                    "splynx": "splynx",
                    "chatwoot": "chatwoot",
                }
                source = source_map.get(str(ticket.source).lower() if ticket.source else "internal", "internal")

                # Map ticket type
                type_map = {
                    "technical": "technical",
                    "billing": "billing",
                    "service": "service",
                    "complaint": "complaint",
                    "support": "support",
                }
                ticket_type = type_map.get(str(ticket.ticket_type).lower() if ticket.ticket_type else "support", "support")

                # Generate ticket number if missing
                ticket_number = ticket.ticket_number or f"TKT-{ticket.id:06d}"

                # Calculate SLA breaches
                now = datetime.utcnow()
                response_breached = False
                resolution_breached = False
                if ticket.response_by and not ticket.first_responded_on:
                    response_breached = ticket.response_by < now
                if ticket.resolution_by and not ticket.resolution_date:
                    resolution_breached = ticket.resolution_by < now

                if dry_run:
                    if verbose:
                        print(f"  [DRY-RUN] Would create unified ticket for ticket #{ticket.id} ({ticket_number})")
                    stats["created"] += 1
                    if ticket.customer_unified_contact_id:
                        stats["linked_contact"] += 1
                    continue

                # Insert unified ticket
                session.execute(text("""
                    INSERT INTO unified_tickets (
                        ticket_number, subject, description,
                        ticket_type, source, status, priority,
                        category, issue_type,
                        unified_contact_id,
                        contact_name, contact_email, contact_phone,
                        assigned_to_id, created_by_id,
                        response_by, resolution_by,
                        first_response_at, resolved_at,
                        response_sla_breached, resolution_sla_breached,
                        resolution, csat_rating, csat_feedback,
                        splynx_id, erpnext_id,
                        legacy_ticket_id,
                        region, base_station,
                        tags,
                        created_at, updated_at
                    ) VALUES (
                        :ticket_number, :subject, :description,
                        :ticket_type, :source, :status, :priority,
                        :category, :issue_type,
                        :unified_contact_id,
                        :contact_name, :contact_email, :contact_phone,
                        :assigned_to_id, :created_by_id,
                        :response_by, :resolution_by,
                        :first_response_at, :resolved_at,
                        :response_sla_breached, :resolution_sla_breached,
                        :resolution, :csat_rating, :csat_feedback,
                        :splynx_id, :erpnext_id,
                        :legacy_ticket_id,
                        :region, :base_station,
                        :tags,
                        :created_at, :updated_at
                    )
                """), {
                    "ticket_number": ticket_number,
                    "subject": ticket.subject or "No subject",
                    "description": ticket.description,
                    "ticket_type": ticket_type,
                    "source": source,
                    "status": status,
                    "priority": priority,
                    "category": ticket.ticket_type,
                    "issue_type": ticket.issue_type,
                    "unified_contact_id": ticket.customer_unified_contact_id,
                    "contact_name": ticket.customer_name,
                    "contact_email": ticket.customer_email,
                    "contact_phone": ticket.customer_phone,
                    "assigned_to_id": ticket.assigned_employee_id,
                    "created_by_id": ticket.employee_id,
                    "response_by": ticket.response_by,
                    "resolution_by": ticket.resolution_by,
                    "first_response_at": ticket.first_responded_on,
                    "resolved_at": ticket.resolution_date,
                    "response_sla_breached": response_breached,
                    "resolution_sla_breached": resolution_breached,
                    "resolution": ticket.resolution or ticket.resolution_details,
                    "csat_rating": ticket.feedback_rating,
                    "csat_feedback": ticket.feedback_text,
                    "splynx_id": ticket.splynx_id,
                    "erpnext_id": ticket.erpnext_id,
                    "legacy_ticket_id": ticket.id,
                    "region": ticket.region,
                    "base_station": ticket.base_station,
                    "tags": ticket.tags,
                    "created_at": ticket.created_at or datetime.utcnow(),
                    "updated_at": ticket.updated_at or datetime.utcnow(),
                })

                stats["created"] += 1
                if ticket.customer_unified_contact_id:
                    stats["linked_contact"] += 1

                if verbose:
                    print(f"  Created unified ticket for ticket #{ticket.id} ({ticket_number})")

            except Exception as e:
                stats["errors"] += 1
                print(f"  ERROR migrating ticket #{ticket.id}: {e}")

        if not dry_run:
            session.commit()

        offset += batch_size
        print(f"  Processed {offset} tickets...")

    return stats


# =============================================================================
# CONVERSATION MIGRATION
# =============================================================================

def migrate_conversations(session: Session, batch_size: int, dry_run: bool, verbose: bool) -> dict:
    """
    Migrate Chatwoot conversations to unified_tickets.

    Priority for linking:
    1. legacy_conversation_id (always set)
    2. chatwoot_conversation_id (chatwoot_id)
    3. unified_contact_id via customer_id → customers.unified_contact_id
    """
    stats = {"created": 0, "skipped": 0, "linked_contact": 0, "errors": 0}

    offset = 0
    while True:
        conversations = session.execute(text("""
            SELECT
                c.id,
                c.chatwoot_id,
                c.customer_id,
                c.subject,
                c.inbox_name,
                c.channel,
                c.status,
                c.priority,
                c.assigned_agent_id,
                c.assigned_agent_name,
                c.assigned_team_id,
                c.assigned_team_name,
                c.employee_id,
                c.labels,
                c.category,
                c.message_count,
                c.first_response_at,
                c.resolved_at,
                c.last_activity_at,
                c.first_response_time_seconds,
                c.resolution_time_seconds,
                c.created_at,
                c.updated_at,
                cust.unified_contact_id as customer_unified_contact_id,
                cust.name as customer_name,
                cust.email as customer_email,
                cust.phone as customer_phone
            FROM conversations c
            LEFT JOIN customers cust ON c.customer_id = cust.id
            WHERE NOT EXISTS (
                SELECT 1 FROM unified_tickets ut WHERE ut.legacy_conversation_id = c.id
            )
            ORDER BY c.id
            LIMIT :limit OFFSET :offset
        """), {"limit": batch_size, "offset": offset}).fetchall()

        if not conversations:
            break

        for conv in conversations:
            try:
                # Map status
                status_map = {
                    "open": "open",
                    "pending": "waiting",
                    "resolved": "resolved",
                    "snoozed": "on_hold",
                }
                status = status_map.get(str(conv.status).lower() if conv.status else "open", "open")

                # Map priority
                priority_map = {
                    "low": "low",
                    "medium": "medium",
                    "high": "high",
                    "urgent": "urgent",
                }
                priority = priority_map.get(str(conv.priority).lower() if conv.priority else "medium", "medium")

                # Map channel
                channel_map = {
                    "email": "email",
                    "whatsapp": "whatsapp",
                    "sms": "sms",
                    "chat": "chat",
                    "web": "chat",
                    "api": "api",
                }
                channel = channel_map.get(str(conv.channel).lower() if conv.channel else "chat", "chat")

                # Generate ticket number
                ticket_number = f"CW-{conv.chatwoot_id or conv.id:06d}"

                # Subject fallback
                subject = conv.subject or f"Conversation from {conv.inbox_name or 'Chatwoot'}"

                if dry_run:
                    if verbose:
                        print(f"  [DRY-RUN] Would create unified ticket for conversation #{conv.id}")
                    stats["created"] += 1
                    if conv.customer_unified_contact_id:
                        stats["linked_contact"] += 1
                    continue

                # Insert unified ticket
                session.execute(text("""
                    INSERT INTO unified_tickets (
                        ticket_number, subject,
                        ticket_type, source, channel, status, priority,
                        category,
                        unified_contact_id,
                        contact_name, contact_email, contact_phone,
                        assigned_to_id, assigned_team,
                        first_response_at, resolved_at,
                        first_response_time_seconds, resolution_time_seconds,
                        chatwoot_conversation_id,
                        legacy_conversation_id,
                        labels,
                        message_count,
                        created_at, updated_at
                    ) VALUES (
                        :ticket_number, :subject,
                        'support', 'chatwoot', :channel, :status, :priority,
                        :category,
                        :unified_contact_id,
                        :contact_name, :contact_email, :contact_phone,
                        :assigned_to_id, :assigned_team,
                        :first_response_at, :resolved_at,
                        :first_response_time_seconds, :resolution_time_seconds,
                        :chatwoot_conversation_id,
                        :legacy_conversation_id,
                        :labels,
                        :message_count,
                        :created_at, :updated_at
                    )
                """), {
                    "ticket_number": ticket_number,
                    "subject": subject,
                    "channel": channel,
                    "status": status,
                    "priority": priority,
                    "category": conv.category,
                    "unified_contact_id": conv.customer_unified_contact_id,
                    "contact_name": conv.customer_name,
                    "contact_email": conv.customer_email,
                    "contact_phone": conv.customer_phone,
                    "assigned_to_id": conv.employee_id,
                    "assigned_team": conv.assigned_team_name,
                    "first_response_at": conv.first_response_at,
                    "resolved_at": conv.resolved_at,
                    "first_response_time_seconds": conv.first_response_time_seconds,
                    "resolution_time_seconds": conv.resolution_time_seconds,
                    "chatwoot_conversation_id": conv.chatwoot_id,
                    "legacy_conversation_id": conv.id,
                    "labels": conv.labels,
                    "message_count": conv.message_count or 0,
                    "created_at": conv.created_at or datetime.utcnow(),
                    "updated_at": conv.updated_at or datetime.utcnow(),
                })

                stats["created"] += 1
                if conv.customer_unified_contact_id:
                    stats["linked_contact"] += 1

                if verbose:
                    print(f"  Created unified ticket for conversation #{conv.id}")

            except Exception as e:
                stats["errors"] += 1
                print(f"  ERROR migrating conversation #{conv.id}: {e}")

        if not dry_run:
            session.commit()

        offset += batch_size
        print(f"  Processed {offset} conversations...")

    return stats


# =============================================================================
# OMNI CONVERSATION MIGRATION
# =============================================================================

def migrate_omni_conversations(session: Session, batch_size: int, dry_run: bool, verbose: bool) -> dict:
    """
    Migrate OmniConversations to unified_tickets.
    """
    stats = {"created": 0, "skipped": 0, "linked_contact": 0, "errors": 0}

    offset = 0
    while True:
        omni_convs = session.execute(text("""
            SELECT
                oc.id,
                oc.customer_id,
                oc.ticket_id,
                oc.lead_id,
                oc.unified_contact_id,
                oc.subject,
                oc.status,
                oc.priority,
                oc.assigned_agent_id,
                oc.assigned_team_id,
                oc.contact_name,
                oc.contact_email,
                oc.contact_phone,
                oc.message_count,
                oc.tags,
                oc.created_at,
                oc.updated_at,
                ch.channel_type
            FROM omni_conversations oc
            LEFT JOIN omni_channels ch ON oc.channel_id = ch.id
            WHERE NOT EXISTS (
                SELECT 1 FROM unified_tickets ut WHERE ut.legacy_omni_conversation_id = oc.id
            )
            ORDER BY oc.id
            LIMIT :limit OFFSET :offset
        """), {"limit": batch_size, "offset": offset}).fetchall()

        if not omni_convs:
            break

        for oc in omni_convs:
            try:
                # Skip if already linked to a ticket (avoid duplicates)
                if oc.ticket_id:
                    stats["skipped"] += 1
                    continue

                # Map status
                status_map = {
                    "open": "open",
                    "pending": "waiting",
                    "resolved": "resolved",
                    "closed": "closed",
                }
                status = status_map.get(str(oc.status).lower() if oc.status else "open", "open")

                # Map priority
                priority_map = {
                    "low": "low",
                    "normal": "medium",
                    "medium": "medium",
                    "high": "high",
                    "urgent": "urgent",
                }
                priority = priority_map.get(str(oc.priority).lower() if oc.priority else "medium", "medium")

                # Map channel
                channel_map = {
                    "email": "email",
                    "whatsapp": "whatsapp",
                    "sms": "sms",
                    "chat": "chat",
                    "web": "chat",
                    "custom": "api",
                }
                channel = channel_map.get(str(oc.channel_type).lower() if oc.channel_type else "chat", "chat")

                # Generate ticket number
                ticket_number = f"OMNI-{oc.id:06d}"

                # Subject fallback
                subject = oc.subject or f"Omnichannel conversation #{oc.id}"

                if dry_run:
                    if verbose:
                        print(f"  [DRY-RUN] Would create unified ticket for omni conversation #{oc.id}")
                    stats["created"] += 1
                    if oc.unified_contact_id:
                        stats["linked_contact"] += 1
                    continue

                # Insert unified ticket
                session.execute(text("""
                    INSERT INTO unified_tickets (
                        ticket_number, subject,
                        ticket_type, source, channel, status, priority,
                        unified_contact_id,
                        contact_name, contact_email, contact_phone,
                        legacy_omni_conversation_id,
                        tags,
                        message_count,
                        created_at, updated_at
                    ) VALUES (
                        :ticket_number, :subject,
                        'support', 'internal', :channel, :status, :priority,
                        :unified_contact_id,
                        :contact_name, :contact_email, :contact_phone,
                        :legacy_omni_conversation_id,
                        :tags,
                        :message_count,
                        :created_at, :updated_at
                    )
                """), {
                    "ticket_number": ticket_number,
                    "subject": subject,
                    "channel": channel,
                    "status": status,
                    "priority": priority,
                    "unified_contact_id": oc.unified_contact_id,
                    "contact_name": oc.contact_name,
                    "contact_email": oc.contact_email,
                    "contact_phone": oc.contact_phone,
                    "legacy_omni_conversation_id": oc.id,
                    "tags": oc.tags,
                    "message_count": oc.message_count or 0,
                    "created_at": oc.created_at or datetime.utcnow(),
                    "updated_at": oc.updated_at or datetime.utcnow(),
                })

                stats["created"] += 1
                if oc.unified_contact_id:
                    stats["linked_contact"] += 1

                if verbose:
                    print(f"  Created unified ticket for omni conversation #{oc.id}")

            except Exception as e:
                stats["errors"] += 1
                print(f"  ERROR migrating omni conversation #{oc.id}: {e}")

        if not dry_run:
            session.commit()

        offset += batch_size
        print(f"  Processed {offset} omni conversations...")

    return stats


# =============================================================================
# CONTACT LINKING (Second Pass)
# =============================================================================

def link_orphan_contacts(session: Session, dry_run: bool, verbose: bool) -> int:
    """
    Second pass: Link unified_tickets without unified_contact_id
    by matching email/phone to unified_contacts.
    """
    if dry_run:
        count = session.execute(text("""
            SELECT COUNT(*) FROM unified_tickets ut
            WHERE ut.unified_contact_id IS NULL
            AND (ut.contact_email IS NOT NULL OR ut.contact_phone IS NOT NULL)
            AND EXISTS (
                SELECT 1 FROM unified_contacts uc
                WHERE uc.email = ut.contact_email
                OR uc.phone = ut.contact_phone
            )
        """)).scalar() or 0
        print(f"  [DRY-RUN] Would link {count} orphan tickets by email/phone")
        return count

    # Link by email
    result1 = session.execute(text("""
        UPDATE unified_tickets ut
        SET unified_contact_id = (
            SELECT uc.id FROM unified_contacts uc
            WHERE uc.email = ut.contact_email
            LIMIT 1
        )
        WHERE ut.unified_contact_id IS NULL
        AND ut.contact_email IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM unified_contacts uc
            WHERE uc.email = ut.contact_email
        )
    """))

    # Link by phone
    result2 = session.execute(text("""
        UPDATE unified_tickets ut
        SET unified_contact_id = (
            SELECT uc.id FROM unified_contacts uc
            WHERE uc.phone = ut.contact_phone
            LIMIT 1
        )
        WHERE ut.unified_contact_id IS NULL
        AND ut.contact_phone IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM unified_contacts uc
            WHERE uc.phone = ut.contact_phone
        )
    """))

    session.commit()
    total = (result1.rowcount or 0) + (result2.rowcount or 0)
    print(f"  Linked {total} orphan tickets by email/phone")
    return total


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Backfill unified_tickets from legacy tickets and conversations"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Only show current status, don't make changes"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of records to process per batch (default: 500)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print details for each migrated record"
    )
    args = parser.parse_args()

    # Create database session
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get current status
        source_counts = get_source_counts(session)
        unified_counts = get_unified_counts(session)
        unmigrated_counts = get_unmigrated_counts(session)

        is_complete = print_status(source_counts, unified_counts, unmigrated_counts)

        if args.status:
            sys.exit(0 if is_complete else 1)

        if is_complete:
            print("No backfill needed - all records have been migrated")
            sys.exit(0)

        mode = "[DRY-RUN] " if args.dry_run else ""
        print(f"\n{mode}Starting ticket backfill (batch size: {args.batch_size})...")

        # Migrate tickets
        print(f"\n{mode}Migrating tickets...")
        ticket_stats = migrate_tickets(session, args.batch_size, args.dry_run, args.verbose)
        print(f"  Tickets: {ticket_stats['created']} created, {ticket_stats['linked_contact']} linked to contacts, {ticket_stats['errors']} errors")

        # Migrate conversations
        print(f"\n{mode}Migrating Chatwoot conversations...")
        conv_stats = migrate_conversations(session, args.batch_size, args.dry_run, args.verbose)
        print(f"  Conversations: {conv_stats['created']} created, {conv_stats['linked_contact']} linked to contacts, {conv_stats['errors']} errors")

        # Migrate omni conversations
        print(f"\n{mode}Migrating omni conversations...")
        omni_stats = migrate_omni_conversations(session, args.batch_size, args.dry_run, args.verbose)
        print(f"  OmniConversations: {omni_stats['created']} created, {omni_stats['skipped']} skipped (linked to ticket), {omni_stats['errors']} errors")

        # Second pass: link orphan contacts
        print(f"\n{mode}Linking orphan tickets to contacts...")
        linked = link_orphan_contacts(session, args.dry_run, args.verbose)

        # Final status
        print("\n" + "=" * 70)
        print("BACKFILL SUMMARY")
        print("=" * 70)
        total_created = ticket_stats['created'] + conv_stats['created'] + omni_stats['created']
        total_linked = ticket_stats['linked_contact'] + conv_stats['linked_contact'] + omni_stats['linked_contact'] + linked
        total_errors = ticket_stats['errors'] + conv_stats['errors'] + omni_stats['errors']

        print(f"  Total unified tickets created:  {total_created:,}")
        print(f"  Total linked to contacts:       {total_linked:,}")
        print(f"  Total errors:                   {total_errors:,}")
        print("=" * 70)

        if not args.dry_run:
            # Show final status
            final_unified = get_unified_counts(session)
            final_unmigrated = get_unmigrated_counts(session)
            print_status(source_counts, final_unified, final_unmigrated)

    except Exception as e:
        session.rollback()
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
