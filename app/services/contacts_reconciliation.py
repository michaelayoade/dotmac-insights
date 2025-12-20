"""
Contacts Reconciliation Service

Compares UnifiedContact data with external systems (Splynx, ERPNext)
to detect drift and generate reconciliation reports.

Usage:
    from app.services.contacts_reconciliation import ContactsReconciliationService

    reconciler = ContactsReconciliationService(db)
    report = reconciler.run_full_reconciliation()

The reconciliation job should be scheduled via Celery Beat to run periodically
(e.g., every hour or daily) depending on sync frequency requirements.
"""
import logging
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.unified_contact import UnifiedContact, ContactType
from app.models.customer import Customer
from app.models.outbound_sync import OutboundSyncLog, SyncStatus, TargetSystem
from app.middleware.metrics import set_contacts_drift
from app.feature_flags import feature_flags

logger = logging.getLogger(__name__)


@dataclass
class FieldMismatch:
    """Represents a field mismatch between UnifiedContact and external system."""
    field_name: str
    unified_value: Any
    external_value: Any


@dataclass
class ContactDrift:
    """Represents drift for a single contact."""
    unified_contact_id: int
    external_system: str
    external_id: str
    mismatched_fields: list[FieldMismatch] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return len(self.mismatched_fields) > 0


@dataclass
class ReconciliationReport:
    """Summary report of reconciliation run."""
    run_at: datetime
    total_contacts: int
    contacts_with_drift: int
    drift_percentage: float
    system: str
    drifted_contacts: list[ContactDrift] = field(default_factory=list)
    missing_in_unified: int = 0
    missing_in_external: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert report to dictionary for JSON serialization."""
        return {
            "run_at": self.run_at.isoformat(),
            "system": self.system,
            "total_contacts": self.total_contacts,
            "contacts_with_drift": self.contacts_with_drift,
            "drift_percentage": round(self.drift_percentage, 2),
            "missing_in_unified": self.missing_in_unified,
            "missing_in_external": self.missing_in_external,
            "errors": self.errors,
            "sample_drifted_contacts": [
                {
                    "unified_contact_id": d.unified_contact_id,
                    "external_id": d.external_id,
                    "mismatched_fields": [
                        {
                            "field": m.field_name,
                            "unified": str(m.unified_value)[:100],
                            "external": str(m.external_value)[:100],
                        }
                        for m in d.mismatched_fields[:5]  # Limit to 5 fields per contact
                    ]
                }
                for d in self.drifted_contacts[:10]  # Limit to 10 contacts in sample
            ]
        }


class ContactsReconciliationService:
    """
    Service for reconciling UnifiedContact with external systems.

    Compares field values and generates drift reports.
    """

    # Fields to compare between UnifiedContact and Customer (legacy)
    CUSTOMER_FIELD_MAPPING = {
        "name": "name",
        "email": "email",
        "phone": "phone",
        "address_line1": "address",
        "city": "city",
        "state": "state",
        "country": "country",
        "splynx_id": "splynx_id",
        "erpnext_id": "erpnext_id",
    }

    def __init__(self, db: Session):
        self.db = db

    def run_full_reconciliation(self) -> dict[str, ReconciliationReport]:
        """
        Run reconciliation against all external systems.

        Returns:
            Dict mapping system name to reconciliation report
        """
        if not feature_flags.CONTACTS_RECONCILIATION_ENABLED:
            logger.info("Reconciliation disabled by feature flag")
            return {}

        reports = {}

        # Reconcile with legacy Customer table (proxy for Splynx data)
        try:
            reports["customer_legacy"] = self.reconcile_with_customer_table()
        except Exception as e:
            logger.error(f"Customer reconciliation failed: {e}")
            reports["customer_legacy"] = ReconciliationReport(
                run_at=datetime.utcnow(),
                total_contacts=0,
                contacts_with_drift=0,
                drift_percentage=0,
                system="customer_legacy",
                errors=[str(e)]
            )

        # Reconcile with outbound systems using sync logs as signal
        try:
            reports["splynx"] = self.reconcile_with_outbound_system(
                system=TargetSystem.SPLYNX.value,
                contact_filter=[ContactType.CUSTOMER, ContactType.CHURNED],
                external_id_field="splynx_id",
                sync_hash_field="splynx_sync_hash",
            )
        except Exception as e:
            logger.error(f"Splynx reconciliation failed: {e}")
            reports["splynx"] = ReconciliationReport(
                run_at=datetime.utcnow(),
                total_contacts=0,
                contacts_with_drift=0,
                drift_percentage=0,
                system="splynx",
                errors=[str(e)]
            )

        try:
            reports["erpnext"] = self.reconcile_with_outbound_system(
                system=TargetSystem.ERPNEXT.value,
                contact_filter=None,  # all contacts
                external_id_field="erpnext_id",
                sync_hash_field="erpnext_sync_hash",
            )
        except Exception as e:
            logger.error(f"ERPNext reconciliation failed: {e}")
            reports["erpnext"] = ReconciliationReport(
                run_at=datetime.utcnow(),
                total_contacts=0,
                contacts_with_drift=0,
                drift_percentage=0,
                system="erpnext",
                errors=[str(e)]
            )

        # Update Prometheus metrics
        for system, report in reports.items():
            set_contacts_drift(system, report.drift_percentage)

        return reports

    def reconcile_with_customer_table(self) -> ReconciliationReport:
        """
        Reconcile UnifiedContact with legacy Customer table.

        This checks that data synced via dual-write is consistent.
        """
        logger.info("Starting reconciliation with Customer table")

        # Get all customer-type unified contacts that have a legacy_customer_id
        unified_customers = self.db.execute(
            select(UnifiedContact).where(
                UnifiedContact.contact_type.in_([ContactType.CUSTOMER, ContactType.CHURNED]),
                UnifiedContact.legacy_customer_id.isnot(None)
            )
        ).scalars().all()

        total = len(unified_customers)
        drifted = []

        for uc in unified_customers:
            # Get corresponding Customer record
            customer = self.db.execute(
                select(Customer).where(Customer.id == uc.legacy_customer_id)
            ).scalar_one_or_none()

            if not customer:
                # Customer missing - this is drift
                drift = ContactDrift(
                    unified_contact_id=uc.id,
                    external_system="customer_legacy",
                    external_id=str(uc.legacy_customer_id),
                    mismatched_fields=[
                        FieldMismatch("record_exists", True, False)
                    ]
                )
                drifted.append(drift)
                continue

            # Compare fields
            mismatches = self._compare_contact_to_customer(uc, customer)
            if mismatches:
                drift = ContactDrift(
                    unified_contact_id=uc.id,
                    external_system="customer_legacy",
                    external_id=str(customer.id),
                    mismatched_fields=mismatches
                )
                drifted.append(drift)

        # Check for orphaned Customers (in Customer but not linked to UnifiedContact)
        orphaned_count = self.db.execute(
            select(func.count(Customer.id)).where(
                Customer.unified_contact_id.is_(None),
                Customer.is_deleted == False
            )
        ).scalar() or 0

        drift_count = len(drifted)
        drift_pct = (drift_count / total * 100) if total > 0 else 0

        report = ReconciliationReport(
            run_at=datetime.utcnow(),
            total_contacts=total,
            contacts_with_drift=drift_count,
            drift_percentage=drift_pct,
            system="customer_legacy",
            drifted_contacts=drifted,
            missing_in_external=len([d for d in drifted if any(
                m.field_name == "record_exists" for m in d.mismatched_fields
            )]),
            missing_in_unified=orphaned_count,
        )

        logger.info(
            f"Reconciliation complete: {total} contacts, {drift_count} with drift "
            f"({drift_pct:.2f}%), {orphaned_count} orphaned customers"
        )

        return report

    def reconcile_with_outbound_system(
        self,
        system: str,
        contact_filter: Optional[list[ContactType]],
        external_id_field: str,
        sync_hash_field: str,
    ) -> ReconciliationReport:
        """
        Reconcile UnifiedContact with outbound sync signals (Splynx/ERPNext).

        Uses outbound_sync_log success entries as a proxy and checks:
        - Missing external_id
        - Missing recent success log
        - Sync hash mismatch between contact and last success
        """
        logger.info(f"Starting reconciliation with outbound system: {system}")

        query = select(UnifiedContact)
        if contact_filter:
            query = query.where(UnifiedContact.contact_type.in_(contact_filter))

        contacts = self.db.execute(query).scalars().all()
        total = len(contacts)
        drifted: list[ContactDrift] = []
        missing_external = 0

        for uc in contacts:
            ext_id = getattr(uc, external_id_field, None)
            mismatches: list[FieldMismatch] = []

            if not ext_id:
                mismatches.append(FieldMismatch("external_id", None, "missing"))
                missing_external += 1

            # Find last successful sync log
            last_success = self.db.execute(
                select(OutboundSyncLog).where(
                    OutboundSyncLog.entity_type == "unified_contact",
                    OutboundSyncLog.entity_id == uc.id,
                    OutboundSyncLog.target_system == system,
                    OutboundSyncLog.status == SyncStatus.SUCCESS.value,
                ).order_by(OutboundSyncLog.completed_at.desc())
            ).scalars().first()

            if not last_success:
                mismatches.append(FieldMismatch("last_success", None, "missing"))
            else:
                # Compare payload hash vs current sync hash to detect drift since last success
                contact_hash = getattr(uc, sync_hash_field, None)
                if contact_hash and last_success.payload_hash and contact_hash != last_success.payload_hash:
                    mismatches.append(FieldMismatch("payload_hash", contact_hash, last_success.payload_hash))

            if mismatches:
                drifted.append(
                    ContactDrift(
                        unified_contact_id=uc.id,
                        external_system=system,
                        external_id=str(ext_id) if ext_id else "",
                        mismatched_fields=mismatches,
                    )
                )

        drift_count = len(drifted)
        drift_pct = (drift_count / total * 100) if total > 0 else 0

        report = ReconciliationReport(
            run_at=datetime.utcnow(),
            total_contacts=total,
            contacts_with_drift=drift_count,
            drift_percentage=drift_pct,
            system=system,
            drifted_contacts=drifted,
            missing_in_external=missing_external,
            missing_in_unified=0,
        )

        logger.info(
            f"Reconciliation for {system} complete: {total} contacts, {drift_count} with drift ({drift_pct:.2f}%), missing_external={missing_external}"
        )

        return report

    def _compare_contact_to_customer(
        self,
        unified: UnifiedContact,
        customer: Customer
    ) -> list[FieldMismatch]:
        """Compare field values between UnifiedContact and Customer."""
        mismatches = []

        for uc_field, cust_field in self.CUSTOMER_FIELD_MAPPING.items():
            uc_value = getattr(unified, uc_field, None)
            cust_value = getattr(customer, cust_field, None)

            # Normalize for comparison
            uc_value = self._normalize_value(uc_value)
            cust_value = self._normalize_value(cust_value)

            if uc_value != cust_value:
                mismatches.append(FieldMismatch(
                    field_name=uc_field,
                    unified_value=uc_value,
                    external_value=cust_value
                ))

        return mismatches

    def _normalize_value(self, value: Any) -> Any:
        """Normalize value for comparison (handle None, whitespace, etc.)."""
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value if value else None
        return value

    def get_drift_summary(self) -> dict:
        """
        Get a quick summary of current drift status.

        Lighter weight than full reconciliation - just counts.
        """
        # Count unified contacts with customer type
        unified_count = self.db.execute(
            select(func.count(UnifiedContact.id)).where(
                UnifiedContact.contact_type.in_([ContactType.CUSTOMER, ContactType.CHURNED])
            )
        ).scalar() or 0

        # Count linked customers
        linked_count = self.db.execute(
            select(func.count(Customer.id)).where(
                Customer.unified_contact_id.isnot(None),
                Customer.is_deleted == False
            )
        ).scalar() or 0

        # Count orphaned (Customer without UnifiedContact link)
        orphaned_count = self.db.execute(
            select(func.count(Customer.id)).where(
                Customer.unified_contact_id.is_(None),
                Customer.is_deleted == False
            )
        ).scalar() or 0

        return {
            "unified_customers": unified_count,
            "linked_customers": linked_count,
            "orphaned_customers": orphaned_count,
            "link_rate": round(linked_count / max(unified_count, 1) * 100, 2),
        }
