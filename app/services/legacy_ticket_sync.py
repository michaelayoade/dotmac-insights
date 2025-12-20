"""
Legacy Ticket Sync Service

Provides synchronization between UnifiedTicket and legacy Ticket/Conversation tables
during the dual-write period. Ensures backwards compatibility while migrating to the
UnifiedTicket model.

Usage:
    from app.services.legacy_ticket_sync import LegacyTicketSync
    from app.feature_flags import feature_flags

    # After creating/updating a UnifiedTicket
    if feature_flags.TICKETS_DUAL_WRITE_ENABLED:
        sync = LegacyTicketSync(db)
        sync.sync_to_legacy_ticket(unified_ticket)

    # After creating/updating a legacy Ticket
    if feature_flags.TICKETS_DUAL_WRITE_ENABLED:
        sync = LegacyTicketSync(db)
        sync.sync_from_legacy_ticket(ticket)
"""
import structlog
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.unified_ticket import (
    UnifiedTicket,
    TicketType,
    TicketSource,
    TicketStatus,
    TicketPriority,
    TicketChannel,
)
from app.models.ticket import Ticket
from app.models.ticket import TicketStatus as LegacyTicketStatus
from app.models.ticket import TicketPriority as LegacyTicketPriority
from app.models.ticket import TicketSource as LegacyTicketSource
from app.models.conversation import Conversation
from app.models.unified_contact import UnifiedContact
from app.middleware.metrics import TICKETS_DUAL_WRITE_FAILURES

logger = structlog.get_logger(__name__)


class LegacyTicketSync:
    """
    Synchronizes UnifiedTicket changes to legacy Ticket and Conversation tables.

    Used during dual-write period to maintain backwards compatibility for systems
    that still read from the legacy tables.
    """

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # UNIFIED → LEGACY SYNC
    # =========================================================================

    def sync_to_legacy_ticket(self, unified: UnifiedTicket) -> Optional[Ticket]:
        """
        Sync a UnifiedTicket to the legacy Ticket table.

        Creates new Ticket if none exists, updates if it does.

        Args:
            unified: The UnifiedTicket to sync

        Returns:
            The synced Ticket record, or None if sync failed
        """
        try:
            # Find existing ticket by legacy_ticket_id or external IDs
            ticket = self._find_legacy_ticket(unified)

            if ticket:
                return self._update_legacy_ticket(ticket, unified)
            else:
                return self._create_legacy_ticket(unified)

        except Exception as e:
            logger.error(
                "ticket_dual_write_failed",
                unified_ticket_id=unified.id,
                direction="to_legacy",
                error=str(e),
            )
            TICKETS_DUAL_WRITE_FAILURES.inc()
            return None

    def sync_from_legacy_ticket(self, ticket: Ticket) -> Optional[UnifiedTicket]:
        """
        Sync a legacy Ticket to UnifiedTicket (reverse sync).

        Used when a Ticket is created/updated directly and we need to
        keep UnifiedTicket in sync.

        Args:
            ticket: The Ticket to sync from

        Returns:
            The synced UnifiedTicket record, or None if sync failed
        """
        try:
            # Find existing unified ticket
            unified = self._find_unified_ticket(ticket)

            if unified:
                return self._update_unified_from_ticket(unified, ticket)
            else:
                return self._create_unified_from_ticket(ticket)

        except Exception as e:
            logger.error(
                "ticket_dual_write_failed",
                legacy_ticket_id=ticket.id,
                direction="from_legacy",
                error=str(e),
            )
            TICKETS_DUAL_WRITE_FAILURES.inc()
            return None

    def sync_from_conversation(self, conversation: Conversation) -> Optional[UnifiedTicket]:
        """
        Sync a Chatwoot Conversation to UnifiedTicket (reverse sync).

        Used when a Conversation is created/updated directly.

        Args:
            conversation: The Conversation to sync from

        Returns:
            The synced UnifiedTicket record, or None if sync failed
        """
        try:
            # Find existing unified ticket by conversation
            unified = self._find_unified_by_conversation(conversation)

            if unified:
                return self._update_unified_from_conversation(unified, conversation)
            else:
                return self._create_unified_from_conversation(conversation)

        except Exception as e:
            logger.error(
                "ticket_dual_write_failed",
                conversation_id=conversation.id,
                direction="from_conversation",
                error=str(e),
            )
            TICKETS_DUAL_WRITE_FAILURES.inc()
            return None

    # =========================================================================
    # FIND HELPERS
    # =========================================================================

    def _find_legacy_ticket(self, unified: UnifiedTicket) -> Optional[Ticket]:
        """Find a Ticket record that corresponds to this UnifiedTicket."""
        # First try by legacy_ticket_id link
        if unified.legacy_ticket_id:
            ticket = self.db.execute(
                select(Ticket).where(Ticket.id == unified.legacy_ticket_id)
            ).scalar_one_or_none()
            if ticket:
                return ticket

        # Try by external IDs
        if unified.splynx_id:
            ticket = self.db.execute(
                select(Ticket).where(Ticket.splynx_id == str(unified.splynx_id))
            ).scalar_one_or_none()
            if ticket:
                return ticket

        if unified.erpnext_id:
            ticket = self.db.execute(
                select(Ticket).where(Ticket.erpnext_id == unified.erpnext_id)
            ).scalar_one_or_none()
            if ticket:
                return ticket

        return None

    def _find_unified_ticket(self, ticket: Ticket) -> Optional[UnifiedTicket]:
        """Find a UnifiedTicket that corresponds to this Ticket."""
        # Try by legacy_ticket_id
        unified = self.db.execute(
            select(UnifiedTicket).where(UnifiedTicket.legacy_ticket_id == ticket.id)
        ).scalar_one_or_none()
        if unified:
            return unified

        # Try by external IDs
        if ticket.splynx_id:
            unified = self.db.execute(
                select(UnifiedTicket).where(UnifiedTicket.splynx_id == int(ticket.splynx_id))
            ).scalar_one_or_none()
            if unified:
                return unified

        if ticket.erpnext_id:
            unified = self.db.execute(
                select(UnifiedTicket).where(UnifiedTicket.erpnext_id == ticket.erpnext_id)
            ).scalar_one_or_none()
            if unified:
                return unified

        return None

    def _find_unified_by_conversation(self, conv: Conversation) -> Optional[UnifiedTicket]:
        """Find a UnifiedTicket for this Conversation."""
        # Try by legacy_conversation_id
        unified = self.db.execute(
            select(UnifiedTicket).where(UnifiedTicket.legacy_conversation_id == conv.id)
        ).scalar_one_or_none()
        if unified:
            return unified

        # Try by chatwoot_conversation_id
        if conv.chatwoot_id:
            unified = self.db.execute(
                select(UnifiedTicket).where(
                    UnifiedTicket.chatwoot_conversation_id == conv.chatwoot_id
                )
            ).scalar_one_or_none()
            if unified:
                return unified

        return None

    # =========================================================================
    # CREATE HELPERS
    # =========================================================================

    def _create_legacy_ticket(self, unified: UnifiedTicket) -> Ticket:
        """Create a new Ticket from UnifiedTicket."""
        # Get customer_id from unified_contact
        customer_id = None
        if unified.unified_contact_id:
            contact = self.db.execute(
                select(UnifiedContact).where(UnifiedContact.id == unified.unified_contact_id)
            ).scalar_one_or_none()
            if contact:
                customer_id = contact.legacy_customer_id

        ticket = Ticket(
            ticket_number=unified.ticket_number,
            subject=unified.subject,
            description=unified.description,
            status=self._map_unified_status_to_legacy(unified.status),
            priority=self._map_unified_priority_to_legacy(unified.priority),
            source=self._map_unified_source_to_legacy(unified.source),
            ticket_type=unified.category,
            issue_type=unified.issue_type,
            customer_id=customer_id,
            customer_name=unified.contact_name,
            customer_email=unified.contact_email,
            customer_phone=unified.contact_phone,
            assigned_employee_id=unified.assigned_to_id,
            employee_id=unified.created_by_id,
            region=unified.region,
            base_station=unified.base_station,
            response_by=unified.response_by,
            resolution_by=unified.resolution_by,
            first_responded_on=unified.first_response_at,
            resolution_date=unified.resolved_at,
            resolution=unified.resolution,
            feedback_rating=unified.csat_rating,
            feedback_text=unified.csat_feedback,
            splynx_id=str(unified.splynx_id) if unified.splynx_id else None,
            erpnext_id=unified.erpnext_id,
            tags=unified.tags,
            opening_date=unified.created_at,
            created_at=unified.created_at or datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(ticket)
        self.db.flush()

        # Update unified with legacy_ticket_id
        unified.legacy_ticket_id = ticket.id

        logger.info(
            "ticket_dual_write_created_legacy",
            unified_ticket_id=unified.id,
            legacy_ticket_id=ticket.id,
        )

        return ticket

    def _create_unified_from_ticket(self, ticket: Ticket) -> UnifiedTicket:
        """Create a new UnifiedTicket from legacy Ticket."""
        # Try to get unified_contact_id from customer
        unified_contact_id = None
        if ticket.customer_id:
            from app.models.customer import Customer
            customer = self.db.execute(
                select(Customer).where(Customer.id == ticket.customer_id)
            ).scalar_one_or_none()
            if customer:
                unified_contact_id = customer.unified_contact_id

        # Generate ticket number if missing
        ticket_number = ticket.ticket_number or f"TKT-{ticket.id:06d}"

        unified = UnifiedTicket(
            ticket_number=ticket_number,
            subject=ticket.subject or "No subject",
            description=ticket.description,
            ticket_type=self._map_legacy_type_to_unified(ticket.ticket_type),
            source=self._map_legacy_source_to_unified(ticket.source),
            status=self._map_legacy_status_to_unified(ticket.status),
            priority=self._map_legacy_priority_to_unified(ticket.priority),
            category=ticket.ticket_type,
            issue_type=ticket.issue_type,
            unified_contact_id=unified_contact_id,
            contact_name=ticket.customer_name,
            contact_email=ticket.customer_email,
            contact_phone=ticket.customer_phone,
            assigned_to_id=ticket.assigned_employee_id,
            created_by_id=ticket.employee_id,
            response_by=ticket.response_by,
            resolution_by=ticket.resolution_by,
            first_response_at=ticket.first_responded_on,
            resolved_at=ticket.resolution_date,
            resolution=ticket.resolution or ticket.resolution_details,
            csat_rating=ticket.feedback_rating,
            csat_feedback=ticket.feedback_text,
            splynx_id=int(ticket.splynx_id) if ticket.splynx_id else None,
            erpnext_id=ticket.erpnext_id,
            legacy_ticket_id=ticket.id,
            region=ticket.region,
            base_station=ticket.base_station,
            tags=ticket.tags,
            created_at=ticket.created_at or datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(unified)
        self.db.flush()

        logger.info(
            "ticket_dual_write_created_unified",
            legacy_ticket_id=ticket.id,
            unified_ticket_id=unified.id,
        )

        return unified

    def _create_unified_from_conversation(self, conv: Conversation) -> UnifiedTicket:
        """Create a new UnifiedTicket from Conversation."""
        # Try to get unified_contact_id from customer
        unified_contact_id = None
        contact_name = None
        contact_email = None
        contact_phone = None

        if conv.customer_id:
            from app.models.customer import Customer
            customer = self.db.execute(
                select(Customer).where(Customer.id == conv.customer_id)
            ).scalar_one_or_none()
            if customer:
                unified_contact_id = customer.unified_contact_id
                contact_name = customer.name
                contact_email = customer.email
                contact_phone = customer.phone

        # Generate ticket number
        ticket_number = f"CW-{conv.chatwoot_id or conv.id:06d}"

        unified = UnifiedTicket(
            ticket_number=ticket_number,
            subject=conv.subject or f"Conversation from {conv.inbox_name or 'Chatwoot'}",
            ticket_type=TicketType.SUPPORT,
            source=TicketSource.CHATWOOT,
            channel=self._map_channel(conv.channel),
            status=self._map_conversation_status_to_unified(conv.status),
            priority=self._map_conversation_priority_to_unified(conv.priority),
            category=conv.category,
            unified_contact_id=unified_contact_id,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            assigned_to_id=conv.employee_id,
            assigned_team=conv.assigned_team_name,
            first_response_at=conv.first_response_at,
            resolved_at=conv.resolved_at,
            first_response_time_seconds=conv.first_response_time_seconds,
            resolution_time_seconds=conv.resolution_time_seconds,
            chatwoot_conversation_id=conv.chatwoot_id,
            legacy_conversation_id=conv.id,
            labels=conv.labels.split(",") if conv.labels else None,
            message_count=conv.message_count or 0,
            created_at=conv.created_at or datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(unified)
        self.db.flush()

        logger.info(
            "ticket_dual_write_created_unified_from_conversation",
            conversation_id=conv.id,
            unified_ticket_id=unified.id,
        )

        return unified

    # =========================================================================
    # UPDATE HELPERS
    # =========================================================================

    def _update_legacy_ticket(self, ticket: Ticket, unified: UnifiedTicket) -> Ticket:
        """Update an existing Ticket from UnifiedTicket."""
        # Get customer_id from unified_contact
        if unified.unified_contact_id:
            contact = self.db.execute(
                select(UnifiedContact).where(UnifiedContact.id == unified.unified_contact_id)
            ).scalar_one_or_none()
            if contact:
                ticket.customer_id = contact.legacy_customer_id

        ticket.ticket_number = unified.ticket_number
        ticket.subject = unified.subject
        ticket.description = unified.description
        ticket.status = self._map_unified_status_to_legacy(unified.status)
        ticket.priority = self._map_unified_priority_to_legacy(unified.priority)
        ticket.source = self._map_unified_source_to_legacy(unified.source)
        ticket.ticket_type = unified.category
        ticket.issue_type = unified.issue_type
        ticket.customer_name = unified.contact_name
        ticket.customer_email = unified.contact_email
        ticket.customer_phone = unified.contact_phone
        ticket.assigned_employee_id = unified.assigned_to_id
        ticket.employee_id = unified.created_by_id
        ticket.region = unified.region
        ticket.base_station = unified.base_station
        ticket.response_by = unified.response_by
        ticket.resolution_by = unified.resolution_by
        ticket.first_responded_on = unified.first_response_at
        ticket.resolution_date = unified.resolved_at
        ticket.resolution = unified.resolution
        ticket.feedback_rating = unified.csat_rating
        ticket.feedback_text = unified.csat_feedback
        ticket.tags = unified.tags
        ticket.updated_at = datetime.utcnow()

        # Update link
        unified.legacy_ticket_id = ticket.id

        logger.info(
            "ticket_dual_write_updated_legacy",
            unified_ticket_id=unified.id,
            legacy_ticket_id=ticket.id,
        )

        return ticket

    def _update_unified_from_ticket(self, unified: UnifiedTicket, ticket: Ticket) -> UnifiedTicket:
        """Update an existing UnifiedTicket from legacy Ticket."""
        # Try to get unified_contact_id from customer
        if ticket.customer_id and not unified.unified_contact_id:
            from app.models.customer import Customer
            customer = self.db.execute(
                select(Customer).where(Customer.id == ticket.customer_id)
            ).scalar_one_or_none()
            if customer:
                unified.unified_contact_id = customer.unified_contact_id

        unified.ticket_number = ticket.ticket_number or unified.ticket_number
        unified.subject = ticket.subject or unified.subject
        unified.description = ticket.description
        unified.ticket_type = self._map_legacy_type_to_unified(ticket.ticket_type)
        unified.source = self._map_legacy_source_to_unified(ticket.source)
        unified.status = self._map_legacy_status_to_unified(ticket.status)
        unified.priority = self._map_legacy_priority_to_unified(ticket.priority)
        unified.category = ticket.ticket_type
        unified.issue_type = ticket.issue_type
        unified.contact_name = ticket.customer_name
        unified.contact_email = ticket.customer_email
        unified.contact_phone = ticket.customer_phone
        unified.assigned_to_id = ticket.assigned_employee_id
        unified.created_by_id = ticket.employee_id
        unified.response_by = ticket.response_by
        unified.resolution_by = ticket.resolution_by
        unified.first_response_at = ticket.first_responded_on
        unified.resolved_at = ticket.resolution_date
        unified.resolution = ticket.resolution or ticket.resolution_details
        unified.csat_rating = ticket.feedback_rating
        unified.csat_feedback = ticket.feedback_text
        unified.region = ticket.region
        unified.base_station = ticket.base_station
        unified.tags = ticket.tags
        unified.updated_at = datetime.utcnow()

        # Don't overwrite external IDs if already set
        if ticket.splynx_id and not unified.splynx_id:
            unified.splynx_id = int(ticket.splynx_id)
        if ticket.erpnext_id and not unified.erpnext_id:
            unified.erpnext_id = ticket.erpnext_id

        # Ensure link
        unified.legacy_ticket_id = ticket.id

        logger.info(
            "ticket_dual_write_updated_unified",
            legacy_ticket_id=ticket.id,
            unified_ticket_id=unified.id,
        )

        return unified

    def _update_unified_from_conversation(
        self,
        unified: UnifiedTicket,
        conv: Conversation
    ) -> UnifiedTicket:
        """Update an existing UnifiedTicket from Conversation."""
        # Try to get unified_contact_id from customer
        if conv.customer_id and not unified.unified_contact_id:
            from app.models.customer import Customer
            customer = self.db.execute(
                select(Customer).where(Customer.id == conv.customer_id)
            ).scalar_one_or_none()
            if customer:
                unified.unified_contact_id = customer.unified_contact_id

        unified.subject = conv.subject or unified.subject
        unified.channel = self._map_channel(conv.channel)
        unified.status = self._map_conversation_status_to_unified(conv.status)
        unified.priority = self._map_conversation_priority_to_unified(conv.priority)
        unified.category = conv.category
        unified.assigned_to_id = conv.employee_id
        unified.assigned_team = conv.assigned_team_name
        unified.first_response_at = conv.first_response_at
        unified.resolved_at = conv.resolved_at
        unified.first_response_time_seconds = conv.first_response_time_seconds
        unified.resolution_time_seconds = conv.resolution_time_seconds
        unified.message_count = conv.message_count or 0
        unified.labels = conv.labels.split(",") if conv.labels else None
        unified.updated_at = datetime.utcnow()

        # Don't overwrite chatwoot_conversation_id if already set
        if conv.chatwoot_id and not unified.chatwoot_conversation_id:
            unified.chatwoot_conversation_id = conv.chatwoot_id

        # Ensure link
        unified.legacy_conversation_id = conv.id

        logger.info(
            "ticket_dual_write_updated_unified_from_conversation",
            conversation_id=conv.id,
            unified_ticket_id=unified.id,
        )

        return unified

    # =========================================================================
    # MAPPING HELPERS
    # =========================================================================

    def _map_unified_status_to_legacy(self, status: TicketStatus) -> LegacyTicketStatus:
        """Map UnifiedTicket status to legacy Ticket status."""
        mapping = {
            TicketStatus.OPEN: LegacyTicketStatus.OPEN,
            TicketStatus.IN_PROGRESS: LegacyTicketStatus.OPEN,
            TicketStatus.WAITING: LegacyTicketStatus.REPLIED,
            TicketStatus.ON_HOLD: LegacyTicketStatus.ON_HOLD,
            TicketStatus.RESOLVED: LegacyTicketStatus.RESOLVED,
            TicketStatus.CLOSED: LegacyTicketStatus.CLOSED,
            TicketStatus.REOPENED: LegacyTicketStatus.OPEN,
        }
        return mapping.get(status, LegacyTicketStatus.OPEN)

    def _map_legacy_status_to_unified(self, status) -> TicketStatus:
        """Map legacy Ticket status to UnifiedTicket status."""
        if status is None:
            return TicketStatus.OPEN

        status_str = str(status.value if hasattr(status, 'value') else status).lower()
        mapping = {
            "open": TicketStatus.OPEN,
            "replied": TicketStatus.WAITING,
            "resolved": TicketStatus.RESOLVED,
            "closed": TicketStatus.CLOSED,
            "on_hold": TicketStatus.ON_HOLD,
        }
        return mapping.get(status_str, TicketStatus.OPEN)

    def _map_unified_priority_to_legacy(self, priority: TicketPriority) -> LegacyTicketPriority:
        """Map UnifiedTicket priority to legacy Ticket priority."""
        mapping = {
            TicketPriority.LOW: LegacyTicketPriority.LOW,
            TicketPriority.MEDIUM: LegacyTicketPriority.MEDIUM,
            TicketPriority.HIGH: LegacyTicketPriority.HIGH,
            TicketPriority.URGENT: LegacyTicketPriority.URGENT,
            TicketPriority.CRITICAL: LegacyTicketPriority.URGENT,
        }
        return mapping.get(priority, LegacyTicketPriority.MEDIUM)

    def _map_legacy_priority_to_unified(self, priority) -> TicketPriority:
        """Map legacy Ticket priority to UnifiedTicket priority."""
        if priority is None:
            return TicketPriority.MEDIUM

        priority_str = str(priority.value if hasattr(priority, 'value') else priority).lower()
        mapping = {
            "low": TicketPriority.LOW,
            "medium": TicketPriority.MEDIUM,
            "high": TicketPriority.HIGH,
            "urgent": TicketPriority.URGENT,
        }
        return mapping.get(priority_str, TicketPriority.MEDIUM)

    def _map_unified_source_to_legacy(self, source: TicketSource) -> LegacyTicketSource:
        """Map UnifiedTicket source to legacy Ticket source."""
        mapping = {
            TicketSource.ERPNEXT: LegacyTicketSource.ERPNEXT,
            TicketSource.SPLYNX: LegacyTicketSource.SPLYNX,
            TicketSource.CHATWOOT: LegacyTicketSource.CHATWOOT,
            TicketSource.EMAIL: LegacyTicketSource.ERPNEXT,
            TicketSource.PHONE: LegacyTicketSource.ERPNEXT,
            TicketSource.WEB: LegacyTicketSource.ERPNEXT,
            TicketSource.API: LegacyTicketSource.ERPNEXT,
            TicketSource.INTERNAL: LegacyTicketSource.ERPNEXT,
        }
        return mapping.get(source, LegacyTicketSource.ERPNEXT)

    def _map_legacy_source_to_unified(self, source) -> TicketSource:
        """Map legacy Ticket source to UnifiedTicket source."""
        if source is None:
            return TicketSource.INTERNAL

        source_str = str(source.value if hasattr(source, 'value') else source).lower()
        mapping = {
            "erpnext": TicketSource.ERPNEXT,
            "splynx": TicketSource.SPLYNX,
            "chatwoot": TicketSource.CHATWOOT,
        }
        return mapping.get(source_str, TicketSource.INTERNAL)

    def _map_legacy_type_to_unified(self, ticket_type: Optional[str]) -> TicketType:
        """Map legacy ticket type string to UnifiedTicket type."""
        if not ticket_type:
            return TicketType.SUPPORT

        type_lower = ticket_type.lower()
        mapping = {
            "technical": TicketType.TECHNICAL,
            "billing": TicketType.BILLING,
            "service": TicketType.SERVICE,
            "complaint": TicketType.COMPLAINT,
            "inquiry": TicketType.INQUIRY,
            "feature": TicketType.FEATURE_REQUEST,
            "bug": TicketType.BUG,
        }
        return mapping.get(type_lower, TicketType.SUPPORT)

    def _map_conversation_status_to_unified(self, status) -> TicketStatus:
        """Map Conversation status to UnifiedTicket status."""
        if status is None:
            return TicketStatus.OPEN

        status_str = str(status.value if hasattr(status, 'value') else status).lower()
        mapping = {
            "open": TicketStatus.OPEN,
            "pending": TicketStatus.WAITING,
            "resolved": TicketStatus.RESOLVED,
            "snoozed": TicketStatus.ON_HOLD,
        }
        return mapping.get(status_str, TicketStatus.OPEN)

    def _map_conversation_priority_to_unified(self, priority) -> TicketPriority:
        """Map Conversation priority to UnifiedTicket priority."""
        if priority is None:
            return TicketPriority.MEDIUM

        priority_str = str(priority.value if hasattr(priority, 'value') else priority).lower()
        mapping = {
            "low": TicketPriority.LOW,
            "medium": TicketPriority.MEDIUM,
            "high": TicketPriority.HIGH,
            "urgent": TicketPriority.URGENT,
        }
        return mapping.get(priority_str, TicketPriority.MEDIUM)

    def _map_channel(self, channel: Optional[str]) -> Optional[TicketChannel]:
        """Map channel string to TicketChannel enum."""
        if not channel:
            return None

        channel_lower = channel.lower()
        mapping = {
            "email": TicketChannel.EMAIL,
            "phone": TicketChannel.PHONE,
            "chat": TicketChannel.CHAT,
            "whatsapp": TicketChannel.WHATSAPP,
            "sms": TicketChannel.SMS,
            "web": TicketChannel.WEB_FORM,
            "api": TicketChannel.API,
        }
        return mapping.get(channel_lower)
