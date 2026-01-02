"""Migrate Customer data to Contact model and link Invoice/Payment.

Revision ID: customer_contact_migration_001
Revises: data_cleanup_001
Create Date: 2026-01-01

This migration:
1. Creates Contact records for Customers without unified_contact_id
2. Links existing Invoices to Contacts via customer.unified_contact_id
3. Links existing Payments to Contacts via customer.unified_contact_id

This completes the migration from dual Customer/Contact models to
Contact as the single source of truth.
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision = 'customer_contact_migration_001'
down_revision = ('perf_indexes_001', 'rbac_seed_001')  # Merge both heads
branch_labels = None
depends_on = None


def upgrade():
    """Migrate customer data to contact model."""

    conn = op.get_bind()

    # Step 1: Create Contact records for Customers without unified_contact_id
    # Map Customer fields to Contact fields
    print("Step 1: Creating Contact records for orphaned Customers...")

    conn.execute(sa.text("""
        INSERT INTO contacts (
            contact_type,
            category,
            status,
            is_organization,
            is_primary_contact,
            is_billing_contact,
            is_decision_maker,
            email_opt_in,
            sms_opt_in,
            whatsapp_opt_in,
            phone_opt_in,
            total_conversations,
            total_tickets,
            total_orders,
            total_invoices,
            name,
            email,
            billing_email,
            phone,
            phone_secondary,
            address_line1,
            address_line2,
            city,
            state,
            postal_code,
            country,
            latitude,
            longitude,
            gps_raw,
            account_number,
            contract_number,
            vat_id,
            billing_type,
            mrr,
            deposit_balance,
            signup_date,
            activation_date,
            cancellation_date,
            contract_end_date,
            notes,
            legacy_customer_id,
            created_at,
            updated_at
        )
        SELECT
            CASE
                WHEN lower(c.status::text) = 'active' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contacttype'::regtype AND lower(enumlabel) = 'customer'
                )::contacttype
                WHEN lower(c.status::text) = 'inactive' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contacttype'::regtype AND lower(enumlabel) = 'churned'
                )::contacttype
                WHEN lower(c.status::text) = 'cancelled' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contacttype'::regtype AND lower(enumlabel) = 'churned'
                )::contacttype
                WHEN lower(c.status::text) = 'prospect' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contacttype'::regtype AND lower(enumlabel) = 'prospect'
                )::contacttype
                ELSE (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contacttype'::regtype AND lower(enumlabel) = 'customer'
                )::contacttype
            END,
            CASE
                WHEN lower(c.customer_type::text) = 'residential' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contactcategory'::regtype AND lower(enumlabel) = 'residential'
                )::contactcategory
                WHEN lower(c.customer_type::text) = 'business' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contactcategory'::regtype AND lower(enumlabel) = 'business'
                )::contactcategory
                WHEN lower(c.customer_type::text) = 'enterprise' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contactcategory'::regtype AND lower(enumlabel) = 'enterprise'
                )::contactcategory
                ELSE (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contactcategory'::regtype AND lower(enumlabel) = 'residential'
                )::contactcategory
            END,
            CASE
                WHEN lower(c.status::text) = 'active' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contactstatus'::regtype AND lower(enumlabel) = 'active'
                )::contactstatus
                WHEN lower(c.status::text) = 'suspended' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contactstatus'::regtype AND lower(enumlabel) = 'suspended'
                )::contactstatus
                ELSE (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'contactstatus'::regtype AND lower(enumlabel) = 'inactive'
                )::contactstatus
            END,
            CASE WHEN lower(c.customer_type::text) IN ('business', 'enterprise') THEN true ELSE false END,
            true,  -- is_primary_contact (migrated customers are primary)
            true,  -- is_billing_contact (migrated customers are billing)
            false, -- is_decision_maker
            true,  -- email_opt_in
            true,  -- sms_opt_in
            true,  -- whatsapp_opt_in
            true,  -- phone_opt_in
            0,     -- total_conversations
            0,     -- total_tickets
            0,     -- total_orders
            0,     -- total_invoices
            c.name,
            c.email,
            c.billing_email,
            c.phone,
            c.phone_secondary,
            c.address,
            c.address_2,
            c.city,
            c.state,
            c.zip_code,
            COALESCE(c.country, 'Nigeria'),
            c.latitude,
            c.longitude,
            c.gps,
            c.account_number,
            c.contract_number,
            c.vat_id,
            CASE
                WHEN lower(c.billing_type::text) = 'prepaid' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'billingtype'::regtype AND lower(enumlabel) = 'prepaid'
                )::billingtype
                WHEN lower(c.billing_type::text) = 'prepaid_monthly' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'billingtype'::regtype AND lower(enumlabel) = 'prepaid_monthly'
                )::billingtype
                WHEN lower(c.billing_type::text) = 'recurring' THEN (
                    SELECT enumlabel FROM pg_enum
                    WHERE enumtypid = 'billingtype'::regtype AND lower(enumlabel) = 'recurring'
                )::billingtype
                ELSE NULL
            END,
            c.mrr,
            c.deposit_balance,
            c.signup_date,
            c.activation_date,
            c.cancellation_date,
            c.contract_end_date,
            c.notes,
            c.id,  -- Store original customer ID for reference
            COALESCE(c.created_at, NOW()),
            NOW()
        FROM customers c
        WHERE c.unified_contact_id IS NULL
          AND c.is_deleted = false
    """))

    # Step 2: Update customers.unified_contact_id to point to new contacts
    print("Step 2: Linking Customers to their new Contact records...")

    conn.execute(sa.text("""
        UPDATE customers c
        SET unified_contact_id = ct.id
        FROM contacts ct
        WHERE ct.legacy_customer_id = c.id
          AND c.unified_contact_id IS NULL
    """))

    # Step 3: Update invoices.contact_id based on customer.unified_contact_id
    print("Step 3: Linking Invoices to Contacts...")

    conn.execute(sa.text("""
        UPDATE invoices i
        SET contact_id = c.unified_contact_id
        FROM customers c
        WHERE i.customer_id = c.id
          AND i.contact_id IS NULL
          AND c.unified_contact_id IS NOT NULL
    """))

    # Step 4: Update payments.contact_id based on customer.unified_contact_id
    print("Step 4: Linking Payments to Contacts...")

    conn.execute(sa.text("""
        UPDATE payments p
        SET contact_id = c.unified_contact_id
        FROM customers c
        WHERE p.customer_id = c.id
          AND p.contact_id IS NULL
          AND c.unified_contact_id IS NOT NULL
    """))

    # Step 5: Report remaining orphans (if any)
    result = conn.execute(sa.text("""
        SELECT
            (SELECT COUNT(*) FROM invoices WHERE contact_id IS NULL AND customer_id IS NOT NULL) as orphan_invoices,
            (SELECT COUNT(*) FROM payments WHERE contact_id IS NULL AND customer_id IS NOT NULL) as orphan_payments,
            (SELECT COUNT(*) FROM customers WHERE unified_contact_id IS NULL AND is_deleted = false) as orphan_customers
    """))
    row = result.fetchone()
    print(f"Remaining orphans: invoices={row[0]}, payments={row[1]}, customers={row[2]}")

    if row[0] > 0 or row[1] > 0:
        print("WARNING: Some records could not be linked. Manual review required.")


def downgrade():
    """Reverse the migration (remove contact links, don't delete contacts)."""

    conn = op.get_bind()

    # Clear contact_id from invoices that were migrated
    conn.execute(sa.text("""
        UPDATE invoices i
        SET contact_id = NULL
        FROM contacts ct
        WHERE i.contact_id = ct.id
          AND ct.legacy_customer_id IS NOT NULL
    """))

    # Clear contact_id from payments that were migrated
    conn.execute(sa.text("""
        UPDATE payments p
        SET contact_id = NULL
        FROM contacts ct
        WHERE p.contact_id = ct.id
          AND ct.legacy_customer_id IS NOT NULL
    """))

    # Clear unified_contact_id from customers that were migrated
    conn.execute(sa.text("""
        UPDATE customers c
        SET unified_contact_id = NULL
        FROM contacts ct
        WHERE c.unified_contact_id = ct.id
          AND ct.legacy_customer_id IS NOT NULL
    """))

    # Note: We don't delete the Contact records to preserve data
    print("Downgrade complete. Contact records preserved for data safety.")
