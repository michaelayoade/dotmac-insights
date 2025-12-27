"""
Unified Contact Enforcement Service

Ensures all contact-related records have unified_contact_id populated.
Used during dual-write period to maintain data integrity before NOT NULL
constraints are enforced at the database level.

Usage:
    from app.services.unified_contact_enforcement import UnifiedContactEnforcement

    # Before creating a Customer
    enforcement = UnifiedContactEnforcement(db)
    unified_id = enforcement.ensure_unified_contact_for_customer(customer_data)
    customer.unified_contact_id = unified_id

Configuration:
    Set UNIFIED_CONTACT_STRICT_MODE=true to raise errors on missing unified_contact_id
    Set UNIFIED_CONTACT_STRICT_MODE=false to auto-create (dual-write mode)
"""
import os
from typing import Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.unified_contact import (
    UnifiedContact, ContactType, ContactCategory, ContactStatus
)


class UnifiedContactEnforcement:
    """
    Service for enforcing unified contact requirements during dual-write period.

    Modes:
    - STRICT (production after cutover): Raises error if unified_contact_id missing
    - LENIENT (dual-write period): Auto-creates UnifiedContact if missing
    """

    def __init__(self, db: Session):
        self.db = db
        self.strict_mode = os.getenv("UNIFIED_CONTACT_STRICT_MODE", "false").lower() == "true"

    def _find_existing_unified_contact(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        splynx_id: Optional[int] = None,
        erpnext_id: Optional[str] = None,
        legacy_customer_id: Optional[int] = None,
        legacy_lead_id: Optional[int] = None,
        legacy_contact_id: Optional[int] = None,
        legacy_inbox_contact_id: Optional[int] = None,
    ) -> Optional[UnifiedContact]:
        """Find existing unified contact by any identifier."""

        # Try legacy IDs first (most specific)
        if legacy_customer_id:
            uc = self.db.execute(
                select(UnifiedContact).where(UnifiedContact.legacy_customer_id == legacy_customer_id)
            ).scalar_one_or_none()
            if uc:
                return uc

        if legacy_lead_id:
            uc = self.db.execute(
                select(UnifiedContact).where(UnifiedContact.legacy_lead_id == legacy_lead_id)
            ).scalar_one_or_none()
            if uc:
                return uc

        if legacy_contact_id:
            uc = self.db.execute(
                select(UnifiedContact).where(UnifiedContact.legacy_contact_id == legacy_contact_id)
            ).scalar_one_or_none()
            if uc:
                return uc

        if legacy_inbox_contact_id:
            uc = self.db.execute(
                select(UnifiedContact).where(UnifiedContact.legacy_inbox_contact_id == legacy_inbox_contact_id)
            ).scalar_one_or_none()
            if uc:
                return uc

        # Try external system IDs
        if splynx_id:
            uc = self.db.execute(
                select(UnifiedContact).where(UnifiedContact.splynx_id == splynx_id)
            ).scalar_one_or_none()
            if uc:
                return uc

        if erpnext_id:
            uc = self.db.execute(
                select(UnifiedContact).where(UnifiedContact.erpnext_id == erpnext_id)
            ).scalar_one_or_none()
            if uc:
                return uc

        # Try email/phone (less specific, may have false positives)
        if email:
            uc = self.db.execute(
                select(UnifiedContact).where(UnifiedContact.email == email)
            ).scalar_one_or_none()
            if uc:
                return uc

        if phone:
            uc = self.db.execute(
                select(UnifiedContact).where(UnifiedContact.phone == phone)
            ).scalar_one_or_none()
            if uc:
                return uc

        return None

    def ensure_unified_contact_for_customer(
        self,
        customer_id: int,
        customer_data: dict[str, Any],
    ) -> int:
        """
        Ensure a UnifiedContact exists for a Customer record.
        Returns the unified_contact_id to use.

        Args:
            customer_id: The Customer.id (for legacy_customer_id linking)
            customer_data: Dict with customer fields (name, email, phone, etc.)

        Returns:
            unified_contact_id to assign to the Customer

        Raises:
            ValueError: In strict mode if no unified contact can be found/created
        """
        # Check if already linked
        existing = self._find_existing_unified_contact(
            email=customer_data.get("email"),
            phone=customer_data.get("phone"),
            splynx_id=customer_data.get("splynx_id"),
            erpnext_id=customer_data.get("erpnext_id"),
            legacy_customer_id=customer_id,
        )

        if existing:
            return existing.id

        if self.strict_mode:
            raise ValueError(
                f"Customer {customer_id} has no unified_contact_id and strict mode is enabled. "
                "Create UnifiedContact first or disable strict mode."
            )

        # Auto-create in lenient mode
        contact_type = self._map_customer_status_to_type(customer_data.get("status", "active"))
        category = self._map_customer_type_to_category(customer_data.get("customer_type", "residential"))
        is_org = customer_data.get("customer_type") != "residential"

        uc = UnifiedContact(
            contact_type=contact_type,
            category=category,
            status=ContactStatus.ACTIVE,
            is_organization=is_org,
            name=customer_data.get("name", "Unknown"),
            company_name=customer_data.get("name") if is_org else None,
            email=customer_data.get("email"),
            phone=customer_data.get("phone"),
            address_line1=customer_data.get("address"),
            city=customer_data.get("city"),
            state=customer_data.get("state"),
            country=customer_data.get("country", "Nigeria"),
            splynx_id=customer_data.get("splynx_id"),
            erpnext_id=customer_data.get("erpnext_id"),
            legacy_customer_id=customer_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(uc)
        self.db.flush()  # Get ID without committing

        return uc.id

    def ensure_unified_contact_for_lead(
        self,
        lead_id: int,
        lead_data: dict[str, Any],
    ) -> int:
        """
        Ensure a UnifiedContact exists for an ERPNextLead record.
        Returns the unified_contact_id to use.
        """
        existing = self._find_existing_unified_contact(
            email=lead_data.get("email_id") or lead_data.get("email"),
            phone=lead_data.get("phone"),
            erpnext_id=lead_data.get("name"),  # ERPNext lead name is the ID
            legacy_lead_id=lead_id,
        )

        if existing:
            return existing.id

        if self.strict_mode:
            raise ValueError(
                f"Lead {lead_id} has no unified_contact_id and strict mode is enabled. "
                "Create UnifiedContact first or disable strict mode."
            )

        # Auto-create in lenient mode
        name = lead_data.get("lead_name") or f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip()
        is_org = bool(lead_data.get("company_name"))

        uc = UnifiedContact(
            contact_type=ContactType.LEAD,
            category=ContactCategory.RESIDENTIAL,
            status=ContactStatus.ACTIVE,
            is_organization=is_org,
            name=name or "Unknown Lead",
            first_name=lead_data.get("first_name"),
            last_name=lead_data.get("last_name"),
            company_name=lead_data.get("company_name"),
            email=lead_data.get("email_id") or lead_data.get("email"),
            phone=lead_data.get("phone"),
            mobile=lead_data.get("mobile_no"),
            city=lead_data.get("city"),
            state=lead_data.get("state"),
            country=lead_data.get("country", "Nigeria"),
            source=lead_data.get("source"),
            industry=lead_data.get("industry"),
            territory=lead_data.get("territory"),
            erpnext_id=lead_data.get("name"),
            legacy_lead_id=lead_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(uc)
        self.db.flush()

        return uc.id

    def ensure_unified_contact_for_crm_contact(
        self,
        contact_id: int,
        contact_data: dict[str, Any],
        parent_customer_id: Optional[int] = None,
    ) -> int:
        """
        Ensure a UnifiedContact exists for a CRM Contact record.
        Returns the unified_contact_id to use.
        """
        existing = self._find_existing_unified_contact(
            email=contact_data.get("email"),
            phone=contact_data.get("phone"),
            legacy_contact_id=contact_id,
        )

        if existing:
            return existing.id

        if self.strict_mode:
            raise ValueError(
                f"CRM Contact {contact_id} has no unified_contact_id and strict mode is enabled. "
                "Create UnifiedContact first or disable strict mode."
            )

        # Find parent unified contact if this is an org contact
        parent_unified_id = None
        if parent_customer_id:
            parent = self._find_existing_unified_contact(legacy_customer_id=parent_customer_id)
            if parent:
                parent_unified_id = parent.id

        # Determine if this should be 'person' (has parent) or 'lead' (standalone)
        contact_type = ContactType.PERSON if parent_unified_id else ContactType.LEAD

        name = contact_data.get("full_name") or f"{contact_data.get('first_name', '')} {contact_data.get('last_name', '')}".strip()

        uc = UnifiedContact(
            contact_type=contact_type,
            category=ContactCategory.RESIDENTIAL,
            status=ContactStatus.ACTIVE if contact_data.get("is_active", True) else ContactStatus.INACTIVE,
            is_organization=False,
            parent_id=parent_unified_id,
            is_primary_contact=contact_data.get("is_primary", False),
            is_billing_contact=contact_data.get("is_billing_contact", False),
            is_decision_maker=contact_data.get("is_decision_maker", False),
            name=name or "Unknown Contact",
            first_name=contact_data.get("first_name"),
            last_name=contact_data.get("last_name"),
            email=contact_data.get("email"),
            phone=contact_data.get("phone"),
            mobile=contact_data.get("mobile"),
            designation=contact_data.get("designation"),
            department=contact_data.get("department"),
            legacy_contact_id=contact_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(uc)
        self.db.flush()

        return uc.id

    def ensure_unified_contact_for_inbox_contact(
        self,
        inbox_contact_id: int,
        inbox_data: dict[str, Any],
    ) -> int:
        """
        Ensure a UnifiedContact exists for an InboxContact record.
        Returns the unified_contact_id to use.
        """
        existing = self._find_existing_unified_contact(
            email=inbox_data.get("email"),
            phone=inbox_data.get("phone"),
            legacy_inbox_contact_id=inbox_contact_id,
            legacy_customer_id=inbox_data.get("customer_id"),
        )

        if existing:
            return existing.id

        if self.strict_mode:
            raise ValueError(
                f"InboxContact {inbox_contact_id} has no unified_contact_id and strict mode is enabled. "
                "Create UnifiedContact first or disable strict mode."
            )

        is_org = bool(inbox_data.get("company"))

        uc = UnifiedContact(
            contact_type=ContactType.LEAD,
            category=ContactCategory.RESIDENTIAL,
            status=ContactStatus.ACTIVE,
            is_organization=is_org,
            name=inbox_data.get("name", "Unknown"),
            company_name=inbox_data.get("company"),
            email=inbox_data.get("email"),
            phone=inbox_data.get("phone"),
            designation=inbox_data.get("job_title"),
            tags=inbox_data.get("tags"),
            legacy_inbox_contact_id=inbox_contact_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(uc)
        self.db.flush()

        return uc.id

    def backfill_missing_unified_contacts(self) -> dict[str, int]:
        """
        Backfill unified_contact_id for all records missing it.
        Returns counts of records updated per table.

        Use this for batch backfill before enforcing NOT NULL.
        """
        from app.models.customer import Customer
        from app.models.omni import InboxContact

        results = {
            "customers_updated": 0,
            "inbox_contacts_updated": 0,
        }

        # Backfill customers
        orphaned_customers = self.db.execute(
            select(Customer).where(Customer.unified_contact_id.is_(None))
        ).scalars().all()

        for customer in orphaned_customers:
            unified_id = self.ensure_unified_contact_for_customer(
                customer.id,
                {
                    "name": customer.name,
                    "email": customer.email,
                    "phone": customer.phone,
                    "status": customer.status,
                    "customer_type": customer.customer_type,
                    "address": customer.address,
                    "city": customer.city,
                    "state": customer.state,
                    "country": customer.country,
                    "splynx_id": customer.splynx_id,
                    "erpnext_id": customer.erpnext_id,
                }
            )
            customer.unified_contact_id = unified_id
            results["customers_updated"] += 1

        # Backfill inbox contacts
        orphaned_inbox = self.db.execute(
            select(InboxContact).where(InboxContact.unified_contact_id.is_(None))
        ).scalars().all()

        for inbox_contact in orphaned_inbox:
            unified_id = self.ensure_unified_contact_for_inbox_contact(
                inbox_contact.id,
                {
                    "name": inbox_contact.name,
                    "email": inbox_contact.email,
                    "phone": inbox_contact.phone,
                    "company": inbox_contact.company,
                    "job_title": inbox_contact.job_title,
                    "tags": inbox_contact.tags,
                    "customer_id": inbox_contact.customer_id,
                }
            )
            inbox_contact.unified_contact_id = unified_id
            results["inbox_contacts_updated"] += 1

        self.db.commit()
        return results

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _map_customer_status_to_type(self, status: str) -> ContactType:
        """Map legacy Customer.status to ContactType."""
        mapping = {
            "prospect": ContactType.LEAD,
            "active": ContactType.CUSTOMER,
            "inactive": ContactType.CHURNED,
            "suspended": ContactType.CUSTOMER,
        }
        return mapping.get(status, ContactType.LEAD)

    def _map_customer_type_to_category(self, customer_type: str) -> ContactCategory:
        """Map legacy Customer.customer_type to ContactCategory."""
        mapping = {
            "residential": ContactCategory.RESIDENTIAL,
            "business": ContactCategory.BUSINESS,
            "enterprise": ContactCategory.ENTERPRISE,
        }
        return mapping.get(customer_type, ContactCategory.RESIDENTIAL)
