"""
Tickets Reconciliation Service

Compares UnifiedTicket data with external systems (Splynx, ERPNext, Chatwoot)
and legacy Ticket table to detect drift and generate reconciliation reports.

Usage:
    from app.services.tickets_reconciliation import TicketsReconciliationService

    reconciler = TicketsReconciliationService(db)
    reports = reconciler.run_full_reconciliation()

The reconciliation job should be scheduled via Celery Beat to run periodically
(e.g., every hour or daily) depending on sync frequency requirements.
"""
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.unified_ticket import UnifiedTicket, TicketStatus, TicketSource
from app.models.ticket import Ticket
from app.models.conversation import Conversation
from app.models.outbound_sync import OutboundSyncLog, SyncStatus, TargetSystem
from app.middleware.metrics import set_tickets_drift
from app.feature_flags import feature_flags

logger = logging.getLogger(__name__)


@dataclass
class FieldMismatch:
    """Represents a field mismatch between UnifiedTicket and external system."""
    field_name: str
    unified_value: any
    external_value: any


@dataclass
class TicketDrift:
    """Represents drift for a single ticket."""
    unified_ticket_id: int
    external_system: str
    external_id: str
    mismatched_fields: list[FieldMismatch] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return len(self.mismatched_fields) > 0


@dataclass
class TicketReconciliationReport:
    """Summary report of ticket reconciliation run."""
    run_at: datetime
    total_tickets: int
    tickets_with_drift: int
    drift_percentage: float
    system: str
    drifted_tickets: list[TicketDrift] = field(default_factory=list)
    missing_in_unified: int = 0
    missing_in_external: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert report to dictionary for JSON serialization."""
        return {
            "run_at": self.run_at.isoformat(),
            "system": self.system,
            "total_tickets": self.total_tickets,
            "tickets_with_drift": self.tickets_with_drift,
            "drift_percentage": round(self.drift_percentage, 2),
            "missing_in_unified": self.missing_in_unified,
            "missing_in_external": self.missing_in_external,
            "errors": self.errors,
            "sample_drifted_tickets": [
                {
                    "unified_ticket_id": d.unified_ticket_id,
                    "external_id": d.external_id,
                    "mismatched_fields": [
                        {
                            "field": m.field_name,
                            "unified": str(m.unified_value)[:100],
                            "external": str(m.external_value)[:100],
                        }
                        for m in d.mismatched_fields[:5]  # Limit to 5 fields per ticket
                    ]
                }
                for d in self.drifted_tickets[:10]  # Limit to 10 tickets in sample
            ]
        }


class TicketsReconciliationService:
    """
    Service for reconciling UnifiedTicket with external systems and legacy tables.

    Compares field values and generates drift reports.
    """

    # Fields to compare between UnifiedTicket and legacy Ticket
    TICKET_FIELD_MAPPING = {
        "subject": "subject",
        "description": "description",
        "status": "status",
        "priority": "priority",
        "contact_name": "customer_name",
        "contact_email": "email",
        "splynx_id": "splynx_id",
        "erpnext_id": "erpnext_id",
    }

    # Fields to compare between UnifiedTicket and Conversation (Chatwoot)
    CONVERSATION_FIELD_MAPPING = {
        "status": "status",
        "contact_name": "contact_name",
        "contact_email": "contact_email",
    }

    def __init__(self, db: Session):
        self.db = db

    def run_full_reconciliation(self) -> dict[str, TicketReconciliationReport]:
        """
        Run reconciliation against all external systems and legacy tables.

        Returns:
            Dict mapping system name to reconciliation report
        """
        if not feature_flags.TICKETS_RECONCILIATION_ENABLED:
            logger.info("Ticket reconciliation disabled by feature flag")
            return {}

        reports = {}

        # Reconcile with legacy Ticket table
        try:
            reports["ticket_legacy"] = self.reconcile_with_ticket_table()
        except Exception as e:
            logger.error(f"Ticket table reconciliation failed: {e}")
            reports["ticket_legacy"] = TicketReconciliationReport(
                run_at=datetime.utcnow(),
                total_tickets=0,
                tickets_with_drift=0,
                drift_percentage=0,
                system="ticket_legacy",
                errors=[str(e)]
            )

        # Reconcile with legacy Conversation table (Chatwoot)
        try:
            reports["conversation_legacy"] = self.reconcile_with_conversation_table()
        except Exception as e:
            logger.error(f"Conversation table reconciliation failed: {e}")
            reports["conversation_legacy"] = TicketReconciliationReport(
                run_at=datetime.utcnow(),
                total_tickets=0,
                tickets_with_drift=0,
                drift_percentage=0,
                system="conversation_legacy",
                errors=[str(e)]
            )

        # Reconcile with outbound systems using sync logs as signal
        try:
            reports["splynx"] = self.reconcile_with_outbound_system(
                system=TargetSystem.SPLYNX.value,
                source_filter=[TicketSource.SPLYNX],
                external_id_field="splynx_id",
                sync_hash_field="splynx_sync_hash",
            )
        except Exception as e:
            logger.error(f"Splynx ticket reconciliation failed: {e}")
            reports["splynx"] = TicketReconciliationReport(
                run_at=datetime.utcnow(),
                total_tickets=0,
                tickets_with_drift=0,
                drift_percentage=0,
                system="splynx",
                errors=[str(e)]
            )

        try:
            reports["erpnext"] = self.reconcile_with_outbound_system(
                system=TargetSystem.ERPNEXT.value,
                source_filter=None,  # all tickets
                external_id_field="erpnext_id",
                sync_hash_field="erpnext_sync_hash",
            )
        except Exception as e:
            logger.error(f"ERPNext ticket reconciliation failed: {e}")
            reports["erpnext"] = TicketReconciliationReport(
                run_at=datetime.utcnow(),
                total_tickets=0,
                tickets_with_drift=0,
                drift_percentage=0,
                system="erpnext",
                errors=[str(e)]
            )

        try:
            reports["chatwoot"] = self.reconcile_with_outbound_system(
                system=TargetSystem.CHATWOOT.value,
                source_filter=[TicketSource.CHATWOOT],
                external_id_field="chatwoot_conversation_id",
                sync_hash_field="chatwoot_sync_hash",
            )
        except Exception as e:
            logger.error(f"Chatwoot ticket reconciliation failed: {e}")
            reports["chatwoot"] = TicketReconciliationReport(
                run_at=datetime.utcnow(),
                total_tickets=0,
                tickets_with_drift=0,
                drift_percentage=0,
                system="chatwoot",
                errors=[str(e)]
            )

        # Update Prometheus metrics
        for system, report in reports.items():
            set_tickets_drift(system, report.drift_percentage)

        return reports

    def reconcile_with_ticket_table(self) -> TicketReconciliationReport:
        """
        Reconcile UnifiedTicket with legacy Ticket table.

        This checks that data synced via dual-write is consistent.
        """
        logger.info("Starting reconciliation with Ticket table")

        # Get all unified tickets that have a legacy_ticket_id
        unified_tickets = self.db.execute(
            select(UnifiedTicket).where(
                UnifiedTicket.legacy_ticket_id.isnot(None),
                UnifiedTicket.is_deleted == False
            )
        ).scalars().all()

        total = len(unified_tickets)
        drifted = []

        for ut in unified_tickets:
            # Get corresponding Ticket record
            ticket = self.db.execute(
                select(Ticket).where(Ticket.id == ut.legacy_ticket_id)
            ).scalar_one_or_none()

            if not ticket:
                # Ticket missing - this is drift
                drift = TicketDrift(
                    unified_ticket_id=ut.id,
                    external_system="ticket_legacy",
                    external_id=str(ut.legacy_ticket_id),
                    mismatched_fields=[
                        FieldMismatch("record_exists", True, False)
                    ]
                )
                drifted.append(drift)
                continue

            # Compare fields
            mismatches = self._compare_ticket_to_legacy(ut, ticket)
            if mismatches:
                drift = TicketDrift(
                    unified_ticket_id=ut.id,
                    external_system="ticket_legacy",
                    external_id=str(ticket.id),
                    mismatched_fields=mismatches
                )
                drifted.append(drift)

        # Check for orphaned Tickets (in Ticket but not linked to UnifiedTicket)
        orphaned_count = self.db.execute(
            select(func.count(Ticket.id)).where(
                Ticket.unified_ticket_id.is_(None)
            )
        ).scalar() or 0

        drift_count = len(drifted)
        drift_pct = (drift_count / total * 100) if total > 0 else 0

        report = TicketReconciliationReport(
            run_at=datetime.utcnow(),
            total_tickets=total,
            tickets_with_drift=drift_count,
            drift_percentage=drift_pct,
            system="ticket_legacy",
            drifted_tickets=drifted,
            missing_in_external=len([d for d in drifted if any(
                m.field_name == "record_exists" for m in d.mismatched_fields
            )]),
            missing_in_unified=orphaned_count,
        )

        logger.info(
            f"Ticket reconciliation complete: {total} tickets, {drift_count} with drift "
            f"({drift_pct:.2f}%), {orphaned_count} orphaned legacy tickets"
        )

        return report

    def reconcile_with_conversation_table(self) -> TicketReconciliationReport:
        """
        Reconcile UnifiedTicket with legacy Conversation table (Chatwoot).

        This checks that Chatwoot conversations are consistent.
        """
        logger.info("Starting reconciliation with Conversation table")

        # Get all unified tickets that have a legacy_conversation_id
        unified_tickets = self.db.execute(
            select(UnifiedTicket).where(
                UnifiedTicket.legacy_conversation_id.isnot(None),
                UnifiedTicket.is_deleted == False
            )
        ).scalars().all()

        total = len(unified_tickets)
        drifted = []

        for ut in unified_tickets:
            # Get corresponding Conversation record
            conversation = self.db.execute(
                select(Conversation).where(Conversation.id == ut.legacy_conversation_id)
            ).scalar_one_or_none()

            if not conversation:
                # Conversation missing - this is drift
                drift = TicketDrift(
                    unified_ticket_id=ut.id,
                    external_system="conversation_legacy",
                    external_id=str(ut.legacy_conversation_id),
                    mismatched_fields=[
                        FieldMismatch("record_exists", True, False)
                    ]
                )
                drifted.append(drift)
                continue

            # Compare fields
            mismatches = self._compare_ticket_to_conversation(ut, conversation)
            if mismatches:
                drift = TicketDrift(
                    unified_ticket_id=ut.id,
                    external_system="conversation_legacy",
                    external_id=str(conversation.id),
                    mismatched_fields=mismatches
                )
                drifted.append(drift)

        # Check for orphaned Conversations
        orphaned_count = self.db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.unified_ticket_id.is_(None)
            )
        ).scalar() or 0

        drift_count = len(drifted)
        drift_pct = (drift_count / total * 100) if total > 0 else 0

        report = TicketReconciliationReport(
            run_at=datetime.utcnow(),
            total_tickets=total,
            tickets_with_drift=drift_count,
            drift_percentage=drift_pct,
            system="conversation_legacy",
            drifted_tickets=drifted,
            missing_in_external=len([d for d in drifted if any(
                m.field_name == "record_exists" for m in d.mismatched_fields
            )]),
            missing_in_unified=orphaned_count,
        )

        logger.info(
            f"Conversation reconciliation complete: {total} tickets, {drift_count} with drift "
            f"({drift_pct:.2f}%), {orphaned_count} orphaned conversations"
        )

        return report

    def reconcile_with_outbound_system(
        self,
        system: str,
        source_filter: Optional[list[TicketSource]],
        external_id_field: str,
        sync_hash_field: str,
    ) -> TicketReconciliationReport:
        """
        Reconcile UnifiedTicket with outbound sync signals (Splynx/ERPNext/Chatwoot).

        Uses outbound_sync_log success entries as a proxy and checks:
        - Missing external_id
        - Missing recent success log
        - Sync hash mismatch between ticket and last success
        """
        logger.info(f"Starting ticket reconciliation with outbound system: {system}")

        query = select(UnifiedTicket).where(UnifiedTicket.is_deleted == False)
        if source_filter:
            query = query.where(UnifiedTicket.source.in_(source_filter))

        tickets = self.db.execute(query).scalars().all()
        total = len(tickets)
        drifted: list[TicketDrift] = []
        missing_external = 0

        for ut in tickets:
            ext_id = getattr(ut, external_id_field, None)
            mismatches: list[FieldMismatch] = []

            if not ext_id:
                mismatches.append(FieldMismatch("external_id", None, "missing"))
                missing_external += 1

            # Find last successful sync log
            last_success = self.db.execute(
                select(OutboundSyncLog).where(
                    OutboundSyncLog.entity_type == "unified_ticket",
                    OutboundSyncLog.entity_id == ut.id,
                    OutboundSyncLog.target_system == system,
                    OutboundSyncLog.status == SyncStatus.SUCCESS.value,
                ).order_by(OutboundSyncLog.completed_at.desc())
            ).scalars().first()

            if not last_success:
                mismatches.append(FieldMismatch("last_success", None, "missing"))
            else:
                # Compare payload hash vs current sync hash to detect drift since last success
                ticket_hash = getattr(ut, sync_hash_field, None)
                if ticket_hash and last_success.payload_hash and ticket_hash != last_success.payload_hash:
                    mismatches.append(FieldMismatch("payload_hash", ticket_hash, last_success.payload_hash))

            if mismatches:
                drifted.append(
                    TicketDrift(
                        unified_ticket_id=ut.id,
                        external_system=system,
                        external_id=str(ext_id) if ext_id else "",
                        mismatched_fields=mismatches,
                    )
                )

        drift_count = len(drifted)
        drift_pct = (drift_count / total * 100) if total > 0 else 0

        report = TicketReconciliationReport(
            run_at=datetime.utcnow(),
            total_tickets=total,
            tickets_with_drift=drift_count,
            drift_percentage=drift_pct,
            system=system,
            drifted_tickets=drifted,
            missing_in_external=missing_external,
            missing_in_unified=0,
        )

        logger.info(
            f"Ticket reconciliation for {system} complete: {total} tickets, "
            f"{drift_count} with drift ({drift_pct:.2f}%), missing_external={missing_external}"
        )

        return report

    def _compare_ticket_to_legacy(
        self,
        unified: UnifiedTicket,
        ticket: Ticket
    ) -> list[FieldMismatch]:
        """Compare field values between UnifiedTicket and legacy Ticket."""
        mismatches = []

        for ut_field, ticket_field in self.TICKET_FIELD_MAPPING.items():
            ut_value = getattr(unified, ut_field, None)
            ticket_value = getattr(ticket, ticket_field, None)

            # Normalize for comparison
            ut_value = self._normalize_value(ut_value)
            ticket_value = self._normalize_value(ticket_value)

            # Handle enum to string comparison
            if hasattr(ut_value, 'value'):
                ut_value = ut_value.value
            if hasattr(ticket_value, 'value'):
                ticket_value = ticket_value.value

            if ut_value != ticket_value:
                mismatches.append(FieldMismatch(
                    field_name=ut_field,
                    unified_value=ut_value,
                    external_value=ticket_value
                ))

        return mismatches

    def _compare_ticket_to_conversation(
        self,
        unified: UnifiedTicket,
        conversation: Conversation
    ) -> list[FieldMismatch]:
        """Compare field values between UnifiedTicket and legacy Conversation."""
        mismatches = []

        for ut_field, conv_field in self.CONVERSATION_FIELD_MAPPING.items():
            ut_value = getattr(unified, ut_field, None)
            conv_value = getattr(conversation, conv_field, None)

            # Normalize for comparison
            ut_value = self._normalize_value(ut_value)
            conv_value = self._normalize_value(conv_value)

            # Handle enum to string comparison
            if hasattr(ut_value, 'value'):
                ut_value = ut_value.value
            if hasattr(conv_value, 'value'):
                conv_value = conv_value.value

            if ut_value != conv_value:
                mismatches.append(FieldMismatch(
                    field_name=ut_field,
                    unified_value=ut_value,
                    external_value=conv_value
                ))

        return mismatches

    def _normalize_value(self, value: any) -> any:
        """Normalize value for comparison (handle None, whitespace, etc.)."""
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value if value else None
        return value

    def get_drift_summary(self) -> dict:
        """
        Get a quick summary of current ticket drift status.

        Lighter weight than full reconciliation - just counts.
        """
        # Count all unified tickets
        unified_count = self.db.execute(
            select(func.count(UnifiedTicket.id)).where(
                UnifiedTicket.is_deleted == False
            )
        ).scalar() or 0

        # Count linked legacy tickets
        linked_ticket_count = self.db.execute(
            select(func.count(Ticket.id)).where(
                Ticket.unified_ticket_id.isnot(None)
            )
        ).scalar() or 0

        # Count orphaned legacy tickets
        orphaned_ticket_count = self.db.execute(
            select(func.count(Ticket.id)).where(
                Ticket.unified_ticket_id.is_(None)
            )
        ).scalar() or 0

        # Count linked conversations
        linked_conv_count = self.db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.unified_ticket_id.isnot(None)
            )
        ).scalar() or 0

        # Count orphaned conversations
        orphaned_conv_count = self.db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.unified_ticket_id.is_(None)
            )
        ).scalar() or 0

        return {
            "unified_tickets": unified_count,
            "linked_legacy_tickets": linked_ticket_count,
            "orphaned_legacy_tickets": orphaned_ticket_count,
            "linked_conversations": linked_conv_count,
            "orphaned_conversations": orphaned_conv_count,
            "ticket_link_rate": round(linked_ticket_count / max(linked_ticket_count + orphaned_ticket_count, 1) * 100, 2),
            "conversation_link_rate": round(linked_conv_count / max(linked_conv_count + orphaned_conv_count, 1) * 100, 2),
        }
