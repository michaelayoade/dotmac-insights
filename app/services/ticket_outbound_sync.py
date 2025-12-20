"""
Ticket Outbound Sync Service

Handles synchronization of UnifiedTicket data to external systems
(Splynx, ERPNext, Chatwoot) with idempotency checking.

Usage:
    from app.services.ticket_outbound_sync import TicketOutboundSyncService

    sync_service = TicketOutboundSyncService(db)
    await sync_service.sync_ticket_to_splynx(ticket)
    await sync_service.sync_ticket_to_erpnext(ticket)
    await sync_service.sync_ticket_to_chatwoot(ticket)
"""
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional, Any, Dict

from sqlalchemy.orm import Session

from app.config import settings
from app.models.unified_ticket import (
    UnifiedTicket, TicketStatus, TicketPriority, TicketType, TicketSource
)
from app.models.outbound_sync import (
    OutboundSyncLog, SyncStatus, SyncOperation, TargetSystem
)
from app.feature_flags import feature_flags
from app.middleware.metrics import record_outbound_sync

logger = logging.getLogger(__name__)


class TicketOutboundSyncService:
    """
    Service for syncing UnifiedTicket to external systems.

    Implements idempotency by:
    1. Computing hash of payload before sending
    2. Comparing to stored hash on entity
    3. Skipping sync if unchanged
    4. Storing sync log for audit trail
    """

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def sync_ticket_to_splynx(self, ticket: UnifiedTicket) -> OutboundSyncLog:
        """
        Sync a UnifiedTicket to Splynx.

        Only syncs tickets that originated from Splynx or have splynx_id.
        Uses idempotency to skip unchanged tickets.

        Returns:
            OutboundSyncLog entry for the operation
        """
        if not feature_flags.TICKETS_OUTBOUND_SYNC_ENABLED:
            logger.debug(f"Ticket outbound sync disabled, skipping ticket {ticket.id}")
            return self._create_skipped_log(
                ticket, TargetSystem.SPLYNX.value, "Ticket outbound sync disabled"
            )

        # Only sync if ticket has Splynx association
        if not ticket.splynx_id and ticket.source != TicketSource.SPLYNX:
            return self._create_skipped_log(
                ticket, TargetSystem.SPLYNX.value,
                f"Ticket not associated with Splynx (source: {ticket.source.value})"
            )

        # Build payload
        payload = self._build_splynx_payload(ticket)
        payload_hash = self._compute_hash(payload)

        # Idempotency check
        if ticket.splynx_sync_hash == payload_hash:
            logger.info(f"Skipping unchanged ticket {ticket.id} for Splynx sync")
            return self._create_skipped_log(
                ticket, TargetSystem.SPLYNX.value, "No changes detected"
            )

        # Create log entry
        idempotency_key = f"splynx:ticket:{ticket.id}:{ticket.updated_at.timestamp()}"
        log = OutboundSyncLog.create_pending(
            entity_type="unified_ticket",
            entity_id=ticket.id,
            target_system=TargetSystem.SPLYNX.value,
            operation=SyncOperation.UPDATE.value if ticket.splynx_id else SyncOperation.CREATE.value,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            request_payload=payload,
        )
        self.db.add(log)

        try:
            # Perform sync
            external_id = self._push_to_splynx(ticket, payload)

            # Update ticket with sync status
            ticket.splynx_sync_hash = payload_hash
            ticket.last_synced_to_splynx = datetime.utcnow()
            if external_id and not ticket.splynx_id:
                ticket.splynx_id = int(external_id)

            log.mark_success(external_id=str(external_id) if external_id else None)
            record_outbound_sync("unified_ticket", "splynx", success=True)
            logger.info(f"Successfully synced ticket {ticket.id} to Splynx")

        except Exception as e:
            log.mark_failed(str(e))
            record_outbound_sync("unified_ticket", "splynx", success=False)
            logger.error(f"Failed to sync ticket {ticket.id} to Splynx: {e}")

        self.db.flush()
        return log

    def sync_ticket_to_erpnext(self, ticket: UnifiedTicket) -> OutboundSyncLog:
        """
        Sync a UnifiedTicket to ERPNext Issue/HD Ticket.

        Syncs all ticket types to ERPNext HD Ticket doctype.
        Uses idempotency to skip unchanged tickets.

        Returns:
            OutboundSyncLog entry for the operation
        """
        if not feature_flags.TICKETS_OUTBOUND_SYNC_ENABLED:
            logger.debug(f"Ticket outbound sync disabled, skipping ticket {ticket.id}")
            return self._create_skipped_log(
                ticket, TargetSystem.ERPNEXT.value, "Ticket outbound sync disabled"
            )

        # Build payload
        payload = self._build_erpnext_payload(ticket)
        payload_hash = self._compute_hash(payload)

        # Idempotency check
        if ticket.erpnext_sync_hash == payload_hash:
            logger.info(f"Skipping unchanged ticket {ticket.id} for ERPNext sync")
            return self._create_skipped_log(
                ticket, TargetSystem.ERPNEXT.value, "No changes detected"
            )

        # Create log entry
        idempotency_key = f"erpnext:ticket:{ticket.id}:{ticket.updated_at.timestamp()}"
        log = OutboundSyncLog.create_pending(
            entity_type="unified_ticket",
            entity_id=ticket.id,
            target_system=TargetSystem.ERPNEXT.value,
            operation=SyncOperation.UPDATE.value if ticket.erpnext_id else SyncOperation.CREATE.value,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            request_payload=payload,
        )
        self.db.add(log)

        try:
            # Perform sync
            external_id = self._push_to_erpnext(ticket, payload)

            # Update ticket with sync status
            ticket.erpnext_sync_hash = payload_hash
            ticket.last_synced_to_erpnext = datetime.utcnow()
            if external_id and not ticket.erpnext_id:
                ticket.erpnext_id = external_id

            log.mark_success(external_id=external_id)
            record_outbound_sync("unified_ticket", "erpnext", success=True)
            logger.info(f"Successfully synced ticket {ticket.id} to ERPNext")

        except Exception as e:
            log.mark_failed(str(e))
            record_outbound_sync("unified_ticket", "erpnext", success=False)
            logger.error(f"Failed to sync ticket {ticket.id} to ERPNext: {e}")

        self.db.flush()
        return log

    def sync_ticket_to_chatwoot(self, ticket: UnifiedTicket) -> OutboundSyncLog:
        """
        Sync a UnifiedTicket to Chatwoot conversation.

        Only syncs tickets that have chatwoot_conversation_id or originated from Chatwoot.
        Creates/updates the conversation in Chatwoot.

        Returns:
            OutboundSyncLog entry for the operation
        """
        if not feature_flags.TICKETS_OUTBOUND_SYNC_ENABLED:
            logger.debug(f"Ticket outbound sync disabled, skipping ticket {ticket.id}")
            return self._create_skipped_log(
                ticket, TargetSystem.CHATWOOT.value, "Ticket outbound sync disabled"
            )

        # Only sync if ticket has Chatwoot association or channel suggests Chatwoot
        if not ticket.chatwoot_conversation_id and ticket.source != TicketSource.CHATWOOT:
            return self._create_skipped_log(
                ticket, TargetSystem.CHATWOOT.value,
                f"Ticket not associated with Chatwoot (source: {ticket.source.value})"
            )

        # Build payload
        payload = self._build_chatwoot_payload(ticket)
        payload_hash = self._compute_hash(payload)

        # Idempotency check
        if ticket.chatwoot_sync_hash == payload_hash:
            logger.info(f"Skipping unchanged ticket {ticket.id} for Chatwoot sync")
            return self._create_skipped_log(
                ticket, TargetSystem.CHATWOOT.value, "No changes detected"
            )

        # Create log entry
        idempotency_key = f"chatwoot:ticket:{ticket.id}:{ticket.updated_at.timestamp()}"
        log = OutboundSyncLog.create_pending(
            entity_type="unified_ticket",
            entity_id=ticket.id,
            target_system=TargetSystem.CHATWOOT.value,
            operation=SyncOperation.UPDATE.value if ticket.chatwoot_conversation_id else SyncOperation.CREATE.value,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            request_payload=payload,
        )
        self.db.add(log)

        try:
            # Perform sync
            external_id = self._push_to_chatwoot(ticket, payload)

            # Update ticket with sync status
            ticket.chatwoot_sync_hash = payload_hash
            ticket.last_synced_to_chatwoot = datetime.utcnow()
            if external_id and not ticket.chatwoot_conversation_id:
                ticket.chatwoot_conversation_id = int(external_id)

            log.mark_success(external_id=str(external_id) if external_id else None)
            record_outbound_sync("unified_ticket", "chatwoot", success=True)
            logger.info(f"Successfully synced ticket {ticket.id} to Chatwoot")

        except Exception as e:
            log.mark_failed(str(e))
            record_outbound_sync("unified_ticket", "chatwoot", success=False)
            logger.error(f"Failed to sync ticket {ticket.id} to Chatwoot: {e}")

        self.db.flush()
        return log

    def sync_ticket_to_all(self, ticket: UnifiedTicket) -> dict[str, OutboundSyncLog]:
        """
        Sync a ticket to all applicable external systems based on source/associations.

        Returns:
            Dict mapping system name to sync log entry
        """
        results = {}

        # Sync to Splynx (if associated)
        if ticket.splynx_id or ticket.source == TicketSource.SPLYNX:
            results["splynx"] = self.sync_ticket_to_splynx(ticket)

        # Sync to ERPNext (all tickets)
        results["erpnext"] = self.sync_ticket_to_erpnext(ticket)

        # Sync to Chatwoot (if associated)
        if ticket.chatwoot_conversation_id or ticket.source == TicketSource.CHATWOOT:
            results["chatwoot"] = self.sync_ticket_to_chatwoot(ticket)

        return results

    def enqueue_sync(
        self,
        entity_id: int,
        operation: str,
        target_systems: Optional[list[str]] = None,
    ) -> list[OutboundSyncLog]:
        """
        Enqueue a ticket sync operation for later processing.

        Creates pending log entries that can be processed by a worker.

        Args:
            entity_id: ID of the unified ticket
            operation: Operation type (create, update, delete)
            target_systems: List of systems to sync to (default: all)

        Returns:
            List of created sync log entries
        """
        if target_systems is None:
            target_systems = [
                TargetSystem.SPLYNX.value,
                TargetSystem.ERPNEXT.value,
                TargetSystem.CHATWOOT.value,
            ]

        logs = []
        timestamp = datetime.utcnow().timestamp()

        for system in target_systems:
            idempotency_key = f"{system}:unified_ticket:{entity_id}:{timestamp}"
            log = OutboundSyncLog.create_pending(
                entity_type="unified_ticket",
                entity_id=entity_id,
                target_system=system,
                operation=operation,
                idempotency_key=idempotency_key,
                payload_hash="",  # Will be computed during processing
            )
            self.db.add(log)
            logs.append(log)

        self.db.flush()
        return logs

    # =========================================================================
    # PAYLOAD BUILDERS
    # =========================================================================

    def _build_splynx_payload(self, ticket: UnifiedTicket) -> dict:
        """Build payload for Splynx ticket API."""
        # Map status
        status_map = {
            TicketStatus.OPEN: "New",
            TicketStatus.IN_PROGRESS: "In Progress",
            TicketStatus.WAITING: "Waiting on Customer",
            TicketStatus.ON_HOLD: "On Hold",
            TicketStatus.RESOLVED: "Resolved",
            TicketStatus.CLOSED: "Closed",
            TicketStatus.REOPENED: "Reopened",
        }
        status = status_map.get(ticket.status, "New")

        # Map priority
        priority_map = {
            TicketPriority.LOW: "low",
            TicketPriority.MEDIUM: "medium",
            TicketPriority.HIGH: "high",
            TicketPriority.URGENT: "urgent",
            TicketPriority.CRITICAL: "critical",
        }
        priority = priority_map.get(ticket.priority, "medium")

        return {
            "subject": ticket.subject,
            "description": ticket.description,
            "status": status,
            "priority": priority,
            "type": ticket.ticket_type.value if ticket.ticket_type else "support",
            "customer_id": ticket.splynx_id,  # Customer link in Splynx
            "assigned_to": None,  # Would need employee mapping
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            "resolution": ticket.resolution,
        }

    def _build_erpnext_payload(self, ticket: UnifiedTicket) -> dict:
        """Build payload for ERPNext HD Ticket/Issue API."""
        # Map status
        status_map = {
            TicketStatus.OPEN: "Open",
            TicketStatus.IN_PROGRESS: "Open",  # ERPNext groups these
            TicketStatus.WAITING: "Replied",
            TicketStatus.ON_HOLD: "Hold",
            TicketStatus.RESOLVED: "Resolved",
            TicketStatus.CLOSED: "Closed",
            TicketStatus.REOPENED: "Open",
        }
        status = status_map.get(ticket.status, "Open")

        # Map priority
        priority_map = {
            TicketPriority.LOW: "Low",
            TicketPriority.MEDIUM: "Medium",
            TicketPriority.HIGH: "High",
            TicketPriority.URGENT: "Urgent",
            TicketPriority.CRITICAL: "Urgent",
        }
        priority = priority_map.get(ticket.priority, "Medium")

        # Map ticket type to ERPNext issue type
        issue_type_map = {
            TicketType.SUPPORT: "Support",
            TicketType.TECHNICAL: "Technical",
            TicketType.BILLING: "Billing",
            TicketType.SERVICE: "Service Request",
            TicketType.COMPLAINT: "Complaint",
            TicketType.INQUIRY: "Question",
            TicketType.FEATURE_REQUEST: "Feature Request",
            TicketType.BUG: "Bug",
        }
        issue_type = issue_type_map.get(ticket.ticket_type, "Support")

        payload = {
            "doctype": "HD Ticket",
            "subject": ticket.subject,
            "description": ticket.description,
            "status": status,
            "priority": priority,
            "ticket_type": issue_type,
            "raised_by": ticket.contact_email,
            "customer": ticket.contact_name,
            "resolution_details": ticket.resolution,
        }

        # Add SLA tracking
        if ticket.response_by:
            payload["response_by"] = ticket.response_by.isoformat()
        if ticket.resolution_by:
            payload["resolution_by"] = ticket.resolution_by.isoformat()

        return payload

    def _build_chatwoot_payload(self, ticket: UnifiedTicket) -> dict:
        """Build payload for Chatwoot conversation API."""
        # Map status to Chatwoot status
        status_map = {
            TicketStatus.OPEN: "open",
            TicketStatus.IN_PROGRESS: "open",
            TicketStatus.WAITING: "snoozed",
            TicketStatus.ON_HOLD: "snoozed",
            TicketStatus.RESOLVED: "resolved",
            TicketStatus.CLOSED: "resolved",
            TicketStatus.REOPENED: "open",
        }
        status = status_map.get(ticket.status, "open")

        # Map priority to Chatwoot
        priority_map = {
            TicketPriority.LOW: "low",
            TicketPriority.MEDIUM: "medium",
            TicketPriority.HIGH: "high",
            TicketPriority.URGENT: "urgent",
            TicketPriority.CRITICAL: "urgent",
        }
        priority = priority_map.get(ticket.priority, None)

        payload: Dict[str, Any] = {
            "status": status,
            "priority": priority,
            # Chatwoot custom attributes for subject/category
            "custom_attributes": {
                "ticket_subject": ticket.subject,
                "ticket_category": ticket.category,
                "ticket_type": ticket.ticket_type.value if ticket.ticket_type else None,
                "ticket_number": ticket.ticket_number,
            },
        }

        # Labels from our labels/tags
        if ticket.labels:
            payload["labels"] = ticket.labels

        return payload

    # =========================================================================
    # SYNC IMPLEMENTATIONS
    # =========================================================================

    def _push_to_splynx(self, ticket: UnifiedTicket, payload: dict) -> Optional[int]:
        """
        Push ticket data to Splynx API.

        In dry-run mode, logs intent only.
        In live mode, makes actual Splynx API call.
        """
        if feature_flags.TICKETS_OUTBOUND_DRY_RUN:
            logger.info(f"[DRY-RUN] Would push ticket to Splynx: ticket_id={ticket.id}, "
                       f"splynx_id={ticket.splynx_id}, subject={ticket.subject[:50]}")
            return ticket.splynx_id

        # Live mode - make actual API call
        import httpx

        if not settings.splynx_api_url:
            raise ValueError("SPLYNX_API_URL not configured")

        headers = {"Content-Type": "application/json"}
        if settings.splynx_auth_basic:
            headers["Authorization"] = f"Basic {settings.splynx_auth_basic}"
        else:
            raise ValueError("Splynx auth not configured (SPLYNX_AUTH_BASIC required)")

        base_url = settings.splynx_api_url.rstrip("/")

        with httpx.Client(timeout=30) as client:
            if ticket.splynx_id:
                # Update existing ticket
                endpoint = f"{base_url}/admin/tickets/ticket/{ticket.splynx_id}"
                response = client.put(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                logger.info(f"Updated Splynx ticket {ticket.splynx_id} for unified ticket {ticket.id}")
                return ticket.splynx_id
            else:
                # Create new ticket
                endpoint = f"{base_url}/admin/tickets/ticket"
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                new_id = data.get("id")
                logger.info(f"Created Splynx ticket {new_id} for unified ticket {ticket.id}")
                return int(new_id) if new_id else None

    def _push_to_erpnext(self, ticket: UnifiedTicket, payload: dict) -> Optional[str]:
        """
        Push ticket data to ERPNext API.

        In dry-run mode, logs intent only.
        In live mode, makes actual ERPNext API call.
        """
        if feature_flags.TICKETS_OUTBOUND_DRY_RUN:
            logger.info(f"[DRY-RUN] Would push ticket to ERPNext: ticket_id={ticket.id}, "
                       f"erpnext_id={ticket.erpnext_id}, subject={ticket.subject[:50]}")
            return ticket.erpnext_id

        # Live mode - make actual API call
        import httpx

        if not settings.erpnext_api_url:
            raise ValueError("ERPNEXT_API_URL not configured")

        if not settings.erpnext_api_key or not settings.erpnext_api_secret:
            raise ValueError("ERPNext auth not configured (API_KEY and API_SECRET required)")

        headers = {
            "Authorization": f"token {settings.erpnext_api_key}:{settings.erpnext_api_secret}",
            "Content-Type": "application/json",
        }
        base_url = settings.erpnext_api_url.rstrip("/")
        doctype = payload.get("doctype", "HD Ticket")

        with httpx.Client(timeout=30) as client:
            if ticket.erpnext_id:
                # Update existing doc
                endpoint = f"{base_url}/api/resource/{doctype}/{ticket.erpnext_id}"
                response = client.put(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                logger.info(f"Updated ERPNext {doctype} {ticket.erpnext_id} for ticket {ticket.id}")
                return ticket.erpnext_id
            else:
                # Create new doc
                endpoint = f"{base_url}/api/resource/{doctype}"
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                new_name = data.get("data", {}).get("name")
                logger.info(f"Created ERPNext {doctype} {new_name} for ticket {ticket.id}")
                return str(new_name) if new_name is not None else None

    def _push_to_chatwoot(self, ticket: UnifiedTicket, payload: dict) -> Optional[int]:
        """
        Push ticket data to Chatwoot API.

        In dry-run mode, logs intent only.
        In live mode, makes actual Chatwoot API call.
        """
        if feature_flags.TICKETS_OUTBOUND_DRY_RUN:
            logger.info(f"[DRY-RUN] Would push ticket to Chatwoot: ticket_id={ticket.id}, "
                       f"conversation_id={ticket.chatwoot_conversation_id}, subject={ticket.subject[:50]}")
            return ticket.chatwoot_conversation_id

        # Live mode - make actual API call
        import httpx

        if not settings.chatwoot_api_url:
            raise ValueError("CHATWOOT_API_URL not configured")

        if not settings.chatwoot_api_token:
            raise ValueError("Chatwoot auth not configured (CHATWOOT_API_TOKEN required)")

        headers = {
            "api_access_token": settings.chatwoot_api_token,
            "Content-Type": "application/json",
        }
        base_url = settings.chatwoot_api_url.rstrip("/")
        account_id = settings.chatwoot_account_id

        if not account_id:
            raise ValueError("CHATWOOT_ACCOUNT_ID not configured")

        with httpx.Client(timeout=30) as client:
            if ticket.chatwoot_conversation_id:
                # Update existing conversation
                endpoint = f"{base_url}/api/v1/accounts/{account_id}/conversations/{ticket.chatwoot_conversation_id}"
                response = client.patch(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                logger.info(f"Updated Chatwoot conversation {ticket.chatwoot_conversation_id} for ticket {ticket.id}")
                return ticket.chatwoot_conversation_id
            else:
                # Cannot create conversation without contact context
                # Chatwoot conversations are typically created via inbox/contact, not directly
                logger.warning(f"Cannot create new Chatwoot conversation for ticket {ticket.id} - "
                             "conversations must be created via contact inbox")
                return None

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _compute_hash(self, payload: dict) -> str:
        """Compute MD5 hash of payload for idempotency comparison."""
        json_str = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()

    def _create_skipped_log(
        self,
        ticket: UnifiedTicket,
        target_system: str,
        reason: str
    ) -> OutboundSyncLog:
        """Create a skipped sync log entry."""
        log = OutboundSyncLog(
            entity_type="unified_ticket",
            entity_id=ticket.id,
            target_system=target_system,
            operation=SyncOperation.UPDATE.value,
            status=SyncStatus.SKIPPED.value,
            error_message=reason,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        self.db.add(log)
        return log
