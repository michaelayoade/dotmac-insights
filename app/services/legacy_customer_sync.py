"""
Legacy Customer Sync Service

Provides synchronization between UnifiedContact and legacy Customer table
during the dual-write period. This ensures backwards compatibility while
migrating to the UnifiedContact model.

Usage:
    from app.services.legacy_customer_sync import LegacyCustomerSync

    # After creating/updating a UnifiedContact
    sync = LegacyCustomerSync(db)
    sync.sync_to_customer(unified_contact)
"""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.unified_contact import (
    UnifiedContact, ContactType, ContactCategory, ContactStatus
)
from app.models.customer import Customer, CustomerStatus, CustomerType


class LegacyCustomerSync:
    """
    Synchronizes UnifiedContact changes to the legacy Customer table.

    Used during dual-write period to maintain backwards compatibility
    for systems that still read from the Customer table.
    """

    def __init__(self, db: Session):
        self.db = db

    def sync_to_customer(self, unified: UnifiedContact) -> Optional[Customer]:
        """
        Sync a UnifiedContact to the legacy Customer table.

        Only syncs if contact_type is CUSTOMER or CHURNED.
        Creates new Customer if none exists, updates if it does.

        Args:
            unified: The UnifiedContact to sync

        Returns:
            The synced Customer record, or None if not applicable
        """
        # Only sync customer/churned types
        if unified.contact_type not in (ContactType.CUSTOMER, ContactType.CHURNED):
            return None

        # Find existing customer by legacy_customer_id or external IDs
        customer = self._find_customer(unified)

        if customer:
            return self._update_customer(customer, unified)
        else:
            return self._create_customer(unified)

    def sync_from_customer(self, customer: Customer) -> Optional[UnifiedContact]:
        """
        Sync a Customer record to UnifiedContact (reverse sync).

        Used when a Customer is created/updated directly and we need
        to keep UnifiedContact in sync.

        Args:
            customer: The Customer to sync from

        Returns:
            The synced UnifiedContact record
        """
        # Find existing unified contact
        unified = self._find_unified_contact(customer)

        if unified:
            return self._update_unified_from_customer(unified, customer)
        else:
            return self._create_unified_from_customer(customer)

    def _find_customer(self, unified: UnifiedContact) -> Optional[Customer]:
        """Find a Customer record that corresponds to this UnifiedContact."""
        # First try by unified_contact_id link
        if unified.legacy_customer_id:
            customer = self.db.execute(
                select(Customer).where(Customer.id == unified.legacy_customer_id)
            ).scalar_one_or_none()
            if customer:
                return customer

        # Try by external IDs
        if unified.splynx_id:
            customer = self.db.execute(
                select(Customer).where(Customer.splynx_id == unified.splynx_id)
            ).scalar_one_or_none()
            if customer:
                return customer

        if unified.erpnext_id:
            customer = self.db.execute(
                select(Customer).where(Customer.erpnext_id == unified.erpnext_id)
            ).scalar_one_or_none()
            if customer:
                return customer

        # Do not match by email to avoid cross-tenant collisions
        return None

    def _find_unified_contact(self, customer: Customer) -> Optional[UnifiedContact]:
        """Find a UnifiedContact that corresponds to this Customer."""
        if customer.unified_contact_id:
            return self.db.execute(
                select(UnifiedContact).where(UnifiedContact.id == customer.unified_contact_id)
            ).scalar_one_or_none()

        # Try by legacy_customer_id
        return self.db.execute(
            select(UnifiedContact).where(UnifiedContact.legacy_customer_id == customer.id)
        ).scalar_one_or_none()

    def _create_customer(self, unified: UnifiedContact) -> Customer:
        """Create a new Customer from UnifiedContact."""
        customer = Customer(
            unified_contact_id=unified.id,
            name=unified.name,
            email=unified.email,
            billing_email=unified.billing_email,
            phone=unified.phone,
            phone_secondary=unified.phone_secondary,
            address=unified.address_line1,
            address_2=unified.address_line2,
            city=unified.city,
            state=unified.state,
            zip_code=unified.postal_code,
            country=unified.country or "Nigeria",
            latitude=unified.latitude,
            longitude=unified.longitude,
            gps=unified.gps_raw,
            customer_type=self._map_category_to_customer_type(unified.category),
            status=self._map_status_to_customer_status(unified.status, unified.contact_type),
            splynx_id=unified.splynx_id,
            erpnext_id=unified.erpnext_id,
            chatwoot_contact_id=unified.chatwoot_contact_id,
            zoho_id=unified.zoho_id,
            account_number=unified.account_number,
            contract_number=unified.contract_number,
            vat_id=unified.vat_id,
            mrr=unified.mrr,
            pop_id=unified.pop_id,
            base_station=unified.base_station,
            signup_date=unified.signup_date,
            activation_date=unified.activation_date,
            cancellation_date=unified.cancellation_date,
            contract_end_date=unified.contract_end_date,
            conversion_date=unified.conversion_date,
            blocking_date=unified.blocking_date,
            days_until_blocking=unified.days_until_blocking,
            deposit_balance=unified.deposit_balance,
            referrer=unified.referrer,
            notes=unified.notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(customer)
        self.db.flush()

        # Update unified with legacy_customer_id
        unified.legacy_customer_id = customer.id

        return customer

    def _update_customer(self, customer: Customer, unified: UnifiedContact) -> Customer:
        """Update an existing Customer from UnifiedContact."""
        customer.unified_contact_id = unified.id
        customer.name = unified.name
        customer.email = unified.email
        customer.billing_email = unified.billing_email
        customer.phone = unified.phone
        customer.phone_secondary = unified.phone_secondary
        customer.address = unified.address_line1
        customer.address_2 = unified.address_line2
        customer.city = unified.city
        customer.state = unified.state
        customer.zip_code = unified.postal_code
        customer.country = unified.country or "Nigeria"
        customer.latitude = unified.latitude
        customer.longitude = unified.longitude
        customer.gps = unified.gps_raw
        customer.customer_type = self._map_category_to_customer_type(unified.category)
        customer.status = self._map_status_to_customer_status(unified.status, unified.contact_type)
        customer.splynx_id = unified.splynx_id
        customer.erpnext_id = unified.erpnext_id
        customer.chatwoot_contact_id = unified.chatwoot_contact_id
        customer.zoho_id = unified.zoho_id
        customer.account_number = unified.account_number
        customer.contract_number = unified.contract_number
        customer.vat_id = unified.vat_id
        customer.mrr = unified.mrr
        customer.pop_id = unified.pop_id
        customer.base_station = unified.base_station
        customer.signup_date = unified.signup_date
        customer.activation_date = unified.activation_date
        customer.cancellation_date = unified.cancellation_date
        customer.contract_end_date = unified.contract_end_date
        customer.conversion_date = unified.conversion_date
        customer.blocking_date = unified.blocking_date
        customer.days_until_blocking = unified.days_until_blocking
        customer.deposit_balance = unified.deposit_balance
        customer.referrer = unified.referrer
        customer.notes = unified.notes
        customer.updated_at = datetime.utcnow()

        # Update link if needed
        unified.legacy_customer_id = customer.id

        return customer

    def _create_unified_from_customer(self, customer: Customer) -> UnifiedContact:
        """Create a new UnifiedContact from Customer."""
        contact_type = ContactType.CUSTOMER
        if customer.status == CustomerStatus.INACTIVE:
            contact_type = ContactType.CHURNED
        elif customer.status == CustomerStatus.PROSPECT:
            contact_type = ContactType.LEAD

        unified = UnifiedContact(
            contact_type=contact_type,
            category=self._map_customer_type_to_category(customer.customer_type),
            status=self._map_customer_status_to_status(customer.status),
            is_organization=customer.customer_type != CustomerType.RESIDENTIAL,
            name=customer.name,
            company_name=customer.name if customer.customer_type != CustomerType.RESIDENTIAL else None,
            email=customer.email,
            billing_email=customer.billing_email,
            phone=customer.phone,
            phone_secondary=customer.phone_secondary,
            address_line1=customer.address,
            address_line2=customer.address_2,
            city=customer.city,
            state=customer.state,
            postal_code=customer.zip_code,
            country=customer.country or "Nigeria",
            latitude=customer.latitude,
            longitude=customer.longitude,
            gps_raw=customer.gps,
            splynx_id=customer.splynx_id,
            erpnext_id=customer.erpnext_id,
            chatwoot_contact_id=customer.chatwoot_contact_id,
            zoho_id=customer.zoho_id,
            legacy_customer_id=customer.id,
            account_number=customer.account_number,
            contract_number=customer.contract_number,
            vat_id=customer.vat_id,
            mrr=customer.mrr,
            pop_id=customer.pop_id,
            base_station=customer.base_station,
            signup_date=customer.signup_date,
            activation_date=customer.activation_date,
            cancellation_date=customer.cancellation_date,
            contract_end_date=customer.contract_end_date,
            conversion_date=customer.conversion_date,
            blocking_date=customer.blocking_date,
            days_until_blocking=customer.days_until_blocking,
            deposit_balance=customer.deposit_balance,
            referrer=customer.referrer,
            notes=customer.notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(unified)
        self.db.flush()

        # Link customer to unified
        customer.unified_contact_id = unified.id

        return unified

    def _update_unified_from_customer(self, unified: UnifiedContact, customer: Customer) -> UnifiedContact:
        """Update an existing UnifiedContact from Customer."""
        # Determine contact type based on status
        contact_type = ContactType.CUSTOMER
        if customer.status == CustomerStatus.INACTIVE:
            contact_type = ContactType.CHURNED
        elif customer.status == CustomerStatus.PROSPECT:
            contact_type = ContactType.LEAD

        unified.contact_type = contact_type
        unified.category = self._map_customer_type_to_category(customer.customer_type)
        unified.status = self._map_customer_status_to_status(customer.status)
        unified.is_organization = customer.customer_type != CustomerType.RESIDENTIAL
        unified.name = customer.name
        unified.company_name = customer.name if customer.customer_type != CustomerType.RESIDENTIAL else None
        unified.email = customer.email
        unified.billing_email = customer.billing_email
        unified.phone = customer.phone
        unified.phone_secondary = customer.phone_secondary
        unified.address_line1 = customer.address
        unified.address_line2 = customer.address_2
        unified.city = customer.city
        unified.state = customer.state
        unified.postal_code = customer.zip_code
        unified.country = customer.country or "Nigeria"
        unified.latitude = customer.latitude
        unified.longitude = customer.longitude
        unified.gps_raw = customer.gps
        unified.splynx_id = customer.splynx_id
        unified.erpnext_id = customer.erpnext_id
        unified.chatwoot_contact_id = customer.chatwoot_contact_id
        unified.zoho_id = customer.zoho_id
        unified.account_number = customer.account_number
        unified.contract_number = customer.contract_number
        unified.vat_id = customer.vat_id
        unified.mrr = customer.mrr
        unified.pop_id = customer.pop_id
        unified.base_station = customer.base_station
        unified.signup_date = customer.signup_date
        unified.activation_date = customer.activation_date
        unified.cancellation_date = customer.cancellation_date
        unified.contract_end_date = customer.contract_end_date
        unified.conversion_date = customer.conversion_date
        unified.blocking_date = customer.blocking_date
        unified.days_until_blocking = customer.days_until_blocking
        unified.deposit_balance = customer.deposit_balance
        unified.referrer = customer.referrer
        unified.notes = customer.notes
        unified.updated_at = datetime.utcnow()

        # Ensure link
        customer.unified_contact_id = unified.id
        unified.legacy_customer_id = customer.id

        return unified

    # =========================================================================
    # MAPPING HELPERS
    # =========================================================================

    def _map_category_to_customer_type(self, category: ContactCategory) -> CustomerType:
        """Map UnifiedContact category to Customer type."""
        mapping = {
            ContactCategory.RESIDENTIAL: CustomerType.RESIDENTIAL,
            ContactCategory.BUSINESS: CustomerType.BUSINESS,
            ContactCategory.ENTERPRISE: CustomerType.ENTERPRISE,
            ContactCategory.GOVERNMENT: CustomerType.ENTERPRISE,
            ContactCategory.NON_PROFIT: CustomerType.BUSINESS,
        }
        return mapping.get(category, CustomerType.RESIDENTIAL)

    def _map_status_to_customer_status(
        self,
        status: ContactStatus,
        contact_type: ContactType
    ) -> CustomerStatus:
        """Map UnifiedContact status to Customer status."""
        if contact_type == ContactType.CHURNED:
            return CustomerStatus.INACTIVE
        if contact_type == ContactType.LEAD:
            return CustomerStatus.PROSPECT

        mapping = {
            ContactStatus.ACTIVE: CustomerStatus.ACTIVE,
            ContactStatus.INACTIVE: CustomerStatus.INACTIVE,
            ContactStatus.SUSPENDED: CustomerStatus.SUSPENDED,
            ContactStatus.DO_NOT_CONTACT: CustomerStatus.INACTIVE,
        }
        return mapping.get(status, CustomerStatus.ACTIVE)

    def _map_customer_type_to_category(self, customer_type: CustomerType) -> ContactCategory:
        """Map Customer type to UnifiedContact category."""
        mapping = {
            CustomerType.RESIDENTIAL: ContactCategory.RESIDENTIAL,
            CustomerType.BUSINESS: ContactCategory.BUSINESS,
            CustomerType.ENTERPRISE: ContactCategory.ENTERPRISE,
        }
        return mapping.get(customer_type, ContactCategory.RESIDENTIAL)

    def _map_customer_status_to_status(self, customer_status: CustomerStatus) -> ContactStatus:
        """Map Customer status to UnifiedContact status."""
        mapping = {
            CustomerStatus.ACTIVE: ContactStatus.ACTIVE,
            CustomerStatus.INACTIVE: ContactStatus.INACTIVE,
            CustomerStatus.SUSPENDED: ContactStatus.SUSPENDED,
            CustomerStatus.PROSPECT: ContactStatus.ACTIVE,
        }
        return mapping.get(customer_status, ContactStatus.ACTIVE)
