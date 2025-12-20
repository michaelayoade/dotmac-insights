"""
Outbound Sync Service

Handles synchronization of UnifiedContact data to external systems
(Splynx, ERPNext) with idempotency checking to prevent duplicate updates.

Usage:
    from app.services.outbound_sync import OutboundSyncService

    sync_service = OutboundSyncService(db)
    await sync_service.sync_contact_to_splynx(contact)
    await sync_service.sync_contact_to_erpnext(contact)
"""
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional, Any, Dict

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import settings
from app.models.unified_contact import UnifiedContact, ContactType, ContactCategory
from app.models.outbound_sync import (
    OutboundSyncLog, SyncStatus, SyncOperation, TargetSystem
)
from app.feature_flags import feature_flags
from app.middleware.metrics import record_outbound_sync

logger = logging.getLogger(__name__)


class OutboundSyncService:
    """
    Service for syncing UnifiedContact to external systems.

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

    def sync_contact_to_splynx(self, contact: UnifiedContact) -> OutboundSyncLog:
        """
        Sync a UnifiedContact to Splynx.

        Only syncs CUSTOMER and CHURNED contacts (Splynx is for customers).
        Uses idempotency to skip unchanged contacts.

        Returns:
            OutboundSyncLog entry for the operation
        """
        if not feature_flags.CONTACTS_OUTBOUND_SYNC_ENABLED:
            logger.debug(f"Outbound sync disabled, skipping contact {contact.id}")
            return self._create_skipped_log(
                contact, TargetSystem.SPLYNX.value, "Outbound sync disabled"
            )

        # Only sync customers
        if contact.contact_type not in (ContactType.CUSTOMER, ContactType.CHURNED):
            return self._create_skipped_log(
                contact, TargetSystem.SPLYNX.value,
                f"Contact type {contact.contact_type.value} not synced to Splynx"
            )

        # Build payload
        payload = self._build_splynx_payload(contact)
        payload_hash = self._compute_hash(payload)

        # Idempotency check
        if contact.splynx_sync_hash == payload_hash:
            logger.info(f"Skipping unchanged contact {contact.id} for Splynx sync")
            return self._create_skipped_log(
                contact, TargetSystem.SPLYNX.value, "No changes detected"
            )

        # Create log entry
        idempotency_key = f"splynx:contact:{contact.id}:{contact.updated_at.timestamp()}"
        log = OutboundSyncLog.create_pending(
            entity_type="unified_contact",
            entity_id=contact.id,
            target_system=TargetSystem.SPLYNX.value,
            operation=SyncOperation.UPDATE.value if contact.splynx_id else SyncOperation.CREATE.value,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            request_payload=payload,
        )
        self.db.add(log)

        try:
            # Perform sync (placeholder - actual Splynx API call would go here)
            external_id = self._push_to_splynx(contact, payload)

            # Update contact with sync status
            contact.splynx_sync_hash = payload_hash
            contact.last_synced_to_splynx = datetime.utcnow()
            if external_id and not contact.splynx_id:
                contact.splynx_id = int(external_id)

            log.mark_success(external_id=str(external_id) if external_id else None)
            record_outbound_sync("unified_contact", "splynx", success=True)
            logger.info(f"Successfully synced contact {contact.id} to Splynx")

        except Exception as e:
            log.mark_failed(str(e))
            record_outbound_sync("unified_contact", "splynx", success=False)
            logger.error(f"Failed to sync contact {contact.id} to Splynx: {e}")

        self.db.flush()
        return log

    def sync_contact_to_erpnext(self, contact: UnifiedContact) -> OutboundSyncLog:
        """
        Sync a UnifiedContact to ERPNext.

        Syncs all contact types to ERPNext CRM.
        Uses idempotency to skip unchanged contacts.

        Returns:
            OutboundSyncLog entry for the operation
        """
        if not feature_flags.CONTACTS_OUTBOUND_SYNC_ENABLED:
            logger.debug(f"Outbound sync disabled, skipping contact {contact.id}")
            return self._create_skipped_log(
                contact, TargetSystem.ERPNEXT.value, "Outbound sync disabled"
            )

        # Build payload
        payload = self._build_erpnext_payload(contact)
        payload_hash = self._compute_hash(payload)

        # Idempotency check
        if contact.erpnext_sync_hash == payload_hash:
            logger.info(f"Skipping unchanged contact {contact.id} for ERPNext sync")
            return self._create_skipped_log(
                contact, TargetSystem.ERPNEXT.value, "No changes detected"
            )

        # Create log entry
        idempotency_key = f"erpnext:contact:{contact.id}:{contact.updated_at.timestamp()}"
        log = OutboundSyncLog.create_pending(
            entity_type="unified_contact",
            entity_id=contact.id,
            target_system=TargetSystem.ERPNEXT.value,
            operation=SyncOperation.UPDATE.value if contact.erpnext_id else SyncOperation.CREATE.value,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            request_payload=payload,
        )
        self.db.add(log)

        try:
            # Perform sync (placeholder - actual ERPNext API call would go here)
            external_id = self._push_to_erpnext(contact, payload)

            # Update contact with sync status
            contact.erpnext_sync_hash = payload_hash
            contact.last_synced_to_erpnext = datetime.utcnow()
            if external_id and not contact.erpnext_id:
                contact.erpnext_id = external_id

            log.mark_success(external_id=external_id)
            record_outbound_sync("unified_contact", "erpnext", success=True)
            logger.info(f"Successfully synced contact {contact.id} to ERPNext")

        except Exception as e:
            log.mark_failed(str(e))
            record_outbound_sync("unified_contact", "erpnext", success=False)
            logger.error(f"Failed to sync contact {contact.id} to ERPNext: {e}")

        self.db.flush()
        return log

    def sync_contact_to_all(self, contact: UnifiedContact) -> dict[str, OutboundSyncLog]:
        """
        Sync a contact to all applicable external systems.

        Returns:
            Dict mapping system name to sync log entry
        """
        results = {}

        # Sync to Splynx (customers only)
        if contact.contact_type in (ContactType.CUSTOMER, ContactType.CHURNED):
            results["splynx"] = self.sync_contact_to_splynx(contact)

        # Sync to ERPNext (all contacts)
        results["erpnext"] = self.sync_contact_to_erpnext(contact)

        return results

    def enqueue_sync(
        self,
        entity_type: str,
        entity_id: int,
        operation: str,
        target_systems: Optional[list[str]] = None,
    ) -> list[OutboundSyncLog]:
        """
        Enqueue a sync operation for later processing.

        Used when immediate sync is not required or when batching.
        Creates pending log entries that can be processed by a worker.

        Args:
            entity_type: Type of entity (e.g., "unified_contact")
            entity_id: ID of the entity
            operation: Operation type (create, update, delete)
            target_systems: List of systems to sync to (default: all)

        Returns:
            List of created sync log entries
        """
        if target_systems is None:
            target_systems = [TargetSystem.SPLYNX.value, TargetSystem.ERPNEXT.value]

        logs = []
        timestamp = datetime.utcnow().timestamp()

        for system in target_systems:
            idempotency_key = f"{system}:{entity_type}:{entity_id}:{timestamp}"
            log = OutboundSyncLog.create_pending(
                entity_type=entity_type,
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
    # RETRY SUPPORT
    # =========================================================================

    def retry_log(self, log: OutboundSyncLog, contact: UnifiedContact) -> OutboundSyncLog:
        """
        Retry a previously failed sync log without creating a new log entry.

        Uses the stored request_payload if present, otherwise rebuilds payload.
        Updates contact sync hashes/timestamps on success.
        """
        target = log.target_system

        # Determine payload and hash
        if target == TargetSystem.SPLYNX.value:
            payload = log.request_payload or self._build_splynx_payload(contact)
            payload_hash = self._compute_hash(payload)
            log.payload_hash = payload_hash
            log.request_payload = payload
            try:
                external_id = self._push_to_splynx(contact, payload)
                contact.splynx_sync_hash = payload_hash
                contact.last_synced_to_splynx = datetime.utcnow()
                if external_id and not contact.splynx_id:
                    contact.splynx_id = int(external_id)
                log.mark_success(external_id=str(external_id) if external_id else None)
                record_outbound_sync("unified_contact", "splynx", success=True)
                logger.info(f"Retry success: contact {contact.id} to Splynx")
            except Exception as e:
                log.mark_failed(str(e))
                record_outbound_sync("unified_contact", "splynx", success=False)
                logger.error(f"Retry failed: contact {contact.id} to Splynx - {e}")

        elif target == TargetSystem.ERPNEXT.value:
            payload = log.request_payload or self._build_erpnext_payload(contact)
            payload_hash = self._compute_hash(payload)
            log.payload_hash = payload_hash
            log.request_payload = payload
            try:
                erpnext_external_id = self._push_to_erpnext(contact, payload)
                contact.erpnext_sync_hash = payload_hash
                contact.last_synced_to_erpnext = datetime.utcnow()
                if erpnext_external_id and not contact.erpnext_id:
                    contact.erpnext_id = erpnext_external_id
                log.mark_success(external_id=erpnext_external_id)
                record_outbound_sync("unified_contact", "erpnext", success=True)
                logger.info(f"Retry success: contact {contact.id} to ERPNext")
            except Exception as e:
                log.mark_failed(str(e))
                record_outbound_sync("unified_contact", "erpnext", success=False)
                logger.error(f"Retry failed: contact {contact.id} to ERPNext - {e}")
        else:
            log.mark_failed(f"Unknown target system: {target}")
            logger.error(f"Retry failed: unknown target {target} for contact {contact.id}")

        self.db.flush()
        return log

    # =========================================================================
    # PAYLOAD BUILDERS
    # =========================================================================

    def _build_splynx_payload(self, contact: UnifiedContact) -> dict:
        """Build payload for Splynx customer API."""
        # Map status
        status = "active"
        if contact.contact_type == ContactType.CHURNED:
            status = "disabled"
        elif contact.status.value == "suspended":
            status = "blocked"
        elif contact.status.value == "inactive":
            status = "disabled"

        # Map category to customer type
        customer_type = "individual"
        if contact.category in (ContactCategory.BUSINESS, ContactCategory.ENTERPRISE):
            customer_type = "business"

        return {
            "name": contact.name,
            "email": contact.email,
            "phone": contact.phone,
            "status": status,
            "customer_type": customer_type,
            "street_1": contact.address_line1,
            "street_2": contact.address_line2,
            "city": contact.city,
            "state": contact.state,
            "zip_code": contact.postal_code,
            "country": contact.country,
            "gps": contact.gps_raw,
            "billing_email": contact.billing_email,
            "partner_id": None,  # Could be mapped if needed
            # Splynx-specific fields
            "login": contact.account_number or contact.email,
        }

    def _build_erpnext_payload(self, contact: UnifiedContact) -> Dict[str, Any]:
        """Build payload for ERPNext Lead/Customer API."""
        # Determine doctype based on contact type
        if contact.contact_type in (ContactType.LEAD, ContactType.PROSPECT):
            doctype = "Lead"
        else:
            doctype = "Customer"

        payload: Dict[str, Any] = {
            "doctype": doctype,
            "lead_name" if doctype == "Lead" else "customer_name": contact.name,
            "email_id": contact.email,
            "phone": contact.phone,
            "mobile_no": contact.mobile,
            "company_name": contact.company_name,
            "territory": contact.territory or "Nigeria",
            "source": contact.source,
        }

        if doctype == "Lead":
            # Lead-specific fields
            payload.update({
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "qualification_status": contact.lead_qualification.value if contact.lead_qualification else None,
                "industry": contact.industry,
            })
        else:
            # Customer-specific fields
            payload.update({
                "customer_type": "Company" if contact.is_organization else "Individual",
                "customer_group": self._map_category_to_customer_group(contact.category),
                "disabled": 1 if contact.contact_type == ContactType.CHURNED else 0,
            })

        # Address (as child doctype)
        if contact.address_line1:
            payload["address"] = {
                "address_line1": contact.address_line1,
                "address_line2": contact.address_line2,
                "city": contact.city,
                "state": contact.state,
                "pincode": contact.postal_code,
                "country": contact.country or "Nigeria",
            }

        return payload

    # =========================================================================
    # SYNC IMPLEMENTATIONS
    # =========================================================================

    def _push_to_splynx(self, contact: UnifiedContact, payload: dict) -> Optional[int]:
        """
        Push contact data to Splynx API.

        In dry-run mode (FF_CONTACTS_OUTBOUND_DRY_RUN=true), logs intent only.
        In live mode, makes actual Splynx API call to upsert customer.
        """
        if feature_flags.CONTACTS_OUTBOUND_DRY_RUN:
            logger.info(f"[DRY-RUN] Would push to Splynx: contact_id={contact.id}, "
                       f"splynx_id={contact.splynx_id}, payload_keys={list(payload.keys())}")
            return contact.splynx_id

        # Live mode - make actual API call
        import httpx
        from app.config import settings

        if not settings.splynx_api_url:
            raise ValueError("SPLYNX_API_URL not configured")

        headers = {"Content-Type": "application/json"}
        if settings.splynx_auth_basic:
            headers["Authorization"] = f"Basic {settings.splynx_auth_basic}"
        else:
            raise ValueError("Splynx auth not configured (SPLYNX_AUTH_BASIC required)")

        base_url = settings.splynx_api_url.rstrip("/")

        with httpx.Client(timeout=30) as client:
            if contact.splynx_id:
                # Update existing customer
                endpoint = f"{base_url}/admin/customers/customer/{contact.splynx_id}"
                response = client.put(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                logger.info(f"Updated Splynx customer {contact.splynx_id} for contact {contact.id}")
                return contact.splynx_id
            else:
                # Create new customer
                endpoint = f"{base_url}/admin/customers/customer"
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                new_id = data.get("id")
                logger.info(f"Created Splynx customer {new_id} for contact {contact.id}")
                return int(new_id) if new_id else None

    def _push_to_erpnext(self, contact: UnifiedContact, payload: dict) -> Optional[str]:
        """
        Push contact data to ERPNext API.

        In dry-run mode (FF_CONTACTS_OUTBOUND_DRY_RUN=true), logs intent only.
        In live mode, makes actual ERPNext API call to upsert Lead/Customer.
        """
        if feature_flags.CONTACTS_OUTBOUND_DRY_RUN:
            logger.info(f"[DRY-RUN] Would push to ERPNext: contact_id={contact.id}, "
                       f"erpnext_id={contact.erpnext_id}, doctype={payload.get('doctype')}")
            return contact.erpnext_id

        # Live mode - make actual API call
        import httpx
        from app.config import settings

        if not settings.erpnext_api_url:
            raise ValueError("ERPNEXT_API_URL not configured")

        if not settings.erpnext_api_key or not settings.erpnext_api_secret:
            raise ValueError("ERPNext auth not configured (API_KEY and API_SECRET required)")

        headers = {
            "Authorization": f"token {settings.erpnext_api_key}:{settings.erpnext_api_secret}",
            "Content-Type": "application/json",
        }
        base_url = settings.erpnext_api_url.rstrip("/")
        doctype = payload.get("doctype", "Customer")

        with httpx.Client(timeout=30) as client:
            if contact.erpnext_id:
                # Update existing doc
                endpoint = f"{base_url}/api/resource/{doctype}/{contact.erpnext_id}"
                response = client.put(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                logger.info(f"Updated ERPNext {doctype} {contact.erpnext_id} for contact {contact.id}")
                return contact.erpnext_id
            else:
                # Create new doc
                endpoint = f"{base_url}/api/resource/{doctype}"
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                new_name: Optional[str] = data.get("data", {}).get("name")
                logger.info(f"Created ERPNext {doctype} {new_name} for contact {contact.id}")
                return new_name

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _compute_hash(self, payload: dict) -> str:
        """Compute MD5 hash of payload for idempotency comparison."""
        # Sort keys for consistent hashing
        json_str = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()

    def _create_skipped_log(
        self,
        contact: UnifiedContact,
        target_system: str,
        reason: str
    ) -> OutboundSyncLog:
        """Create a skipped sync log entry."""
        log = OutboundSyncLog(
            entity_type="unified_contact",
            entity_id=contact.id,
            target_system=target_system,
            operation=SyncOperation.UPDATE.value,
            status=SyncStatus.SKIPPED.value,
            error_message=reason,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        self.db.add(log)
        return log

    def _map_category_to_customer_group(self, category: ContactCategory) -> str:
        """Map contact category to ERPNext customer group."""
        mapping = {
            ContactCategory.RESIDENTIAL: "Individual",
            ContactCategory.BUSINESS: "Commercial",
            ContactCategory.ENTERPRISE: "Enterprise",
            ContactCategory.GOVERNMENT: "Government",
            ContactCategory.NON_PROFIT: "Non-Profit",
        }
        return mapping.get(category, "Individual")
