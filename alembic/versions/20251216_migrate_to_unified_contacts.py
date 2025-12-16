"""Migrate existing contacts to unified_contacts

This migration:
1. Adds unified_contact_id columns to all related tables
2. Creates staging tables to de-duplicate source data
3. Migrates data from Customer, ERPNextLead, Contact (CRM), InboxContact
   into the unified_contacts table with conflict handling
4. Links original records to their new unified_contact records
5. Logs any collisions/skipped records for review

Revision ID: uc002_migrate_contacts
Revises: uc001_unified_contact
Create Date: 2025-12-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

revision = 'uc002_migrate_contacts'
down_revision = 'uc001_unified_contact'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name)"
    ), {"table_name": table_name})
    return result.scalar()


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    result = conn.execute(sa.text(
        """SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = :table_name AND column_name = :column_name
        )"""
    ), {"table_name": table_name, "column_name": column_name})
    return result.scalar()


def upgrade() -> None:
    # =========================================================================
    # STEP 0: Create collision log table for tracking skipped duplicates
    # =========================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS unified_contact_migration_log (
            id SERIAL PRIMARY KEY,
            source_table VARCHAR(100) NOT NULL,
            source_id INTEGER NOT NULL,
            conflict_type VARCHAR(100) NOT NULL,
            conflict_value TEXT,
            existing_unified_id INTEGER,
            logged_at TIMESTAMP DEFAULT NOW(),
            resolved BOOLEAN DEFAULT FALSE,
            resolution_notes TEXT
        )
    """)

    # =========================================================================
    # STEP 1: Add unified_contact_id columns to related tables (nullable for now)
    # Only add to tables that exist - other migrations may create them later
    # =========================================================================

    # Add to customers table
    if table_exists('customers') and not column_exists('customers', 'unified_contact_id'):
        op.add_column('customers', sa.Column(
            'unified_contact_id', sa.Integer(),
            sa.ForeignKey('unified_contacts.id'),
            nullable=True
        ))
        op.create_index('ix_customers_unified_contact_id', 'customers', ['unified_contact_id'])

    # Add to opportunities table (created by CRM migration)
    if table_exists('opportunities') and not column_exists('opportunities', 'unified_contact_id'):
        op.add_column('opportunities', sa.Column(
            'unified_contact_id', sa.Integer(),
            sa.ForeignKey('unified_contacts.id'),
            nullable=True
        ))
        op.create_index('ix_opportunities_unified_contact_id', 'opportunities', ['unified_contact_id'])

    # Add to activities table (created by CRM migration)
    if table_exists('activities') and not column_exists('activities', 'unified_contact_id'):
        op.add_column('activities', sa.Column(
            'unified_contact_id', sa.Integer(),
            sa.ForeignKey('unified_contacts.id'),
            nullable=True
        ))
        op.create_index('ix_activities_unified_contact_id', 'activities', ['unified_contact_id'])

    # Add to contacts table (CRM - created by CRM migration)
    if table_exists('contacts') and not column_exists('contacts', 'unified_contact_id'):
        op.add_column('contacts', sa.Column(
            'unified_contact_id', sa.Integer(),
            sa.ForeignKey('unified_contacts.id'),
            nullable=True
        ))
        op.create_index('ix_contacts_unified_contact_id', 'contacts', ['unified_contact_id'])

    # Add to omni_conversations table
    if table_exists('omni_conversations') and not column_exists('omni_conversations', 'unified_contact_id'):
        op.add_column('omni_conversations', sa.Column(
            'unified_contact_id', sa.Integer(),
            sa.ForeignKey('unified_contacts.id'),
            nullable=True
        ))
        op.create_index('ix_omni_conversations_unified_contact_id', 'omni_conversations', ['unified_contact_id'])

    # Add to omni_participants table
    if table_exists('omni_participants') and not column_exists('omni_participants', 'unified_contact_id'):
        op.add_column('omni_participants', sa.Column(
            'unified_contact_id', sa.Integer(),
            sa.ForeignKey('unified_contacts.id'),
            nullable=True
        ))
        op.create_index('ix_omni_participants_unified_contact_id', 'omni_participants', ['unified_contact_id'])

    # Add to inbox_contacts table (created by inbox enhancements migration)
    if table_exists('inbox_contacts') and not column_exists('inbox_contacts', 'unified_contact_id'):
        op.add_column('inbox_contacts', sa.Column(
            'unified_contact_id', sa.Integer(),
            sa.ForeignKey('unified_contacts.id'),
            nullable=True
        ))
        op.create_index('ix_inbox_contacts_unified_contact_id', 'inbox_contacts', ['unified_contact_id'])

    # Add to erpnext_leads table
    if table_exists('erpnext_leads') and not column_exists('erpnext_leads', 'unified_contact_id'):
        op.add_column('erpnext_leads', sa.Column(
            'unified_contact_id', sa.Integer(),
            sa.ForeignKey('unified_contacts.id'),
            nullable=True
        ))
        op.create_index('ix_erpnext_leads_unified_contact_id', 'erpnext_leads', ['unified_contact_id'])

    # =========================================================================
    # STEP 2: Create staging table for Customer data with de-duplication
    # =========================================================================
    op.execute("""
        CREATE TEMP TABLE customer_staging AS
        SELECT DISTINCT ON (
            COALESCE(splynx_id::text, 'no_splynx_' || id::text),
            COALESCE(NULLIF(erpnext_id, ''), 'no_erpnext_' || id::text)
        )
            id,
            status,
            customer_type,
            name,
            email,
            billing_email,
            phone,
            phone_secondary,
            address,
            address_2,
            city,
            state,
            zip_code,
            country,
            latitude,
            longitude,
            gps,
            splynx_id,
            erpnext_id,
            chatwoot_contact_id,
            zoho_id,
            account_number,
            contract_number,
            vat_id,
            billing_type,
            mrr,
            blocking_date,
            days_until_blocking,
            deposit_balance,
            added_by_id,
            pop_id,
            base_station,
            signup_date,
            activation_date,
            cancellation_date,
            contract_end_date,
            conversion_date,
            referrer,
            labels,
            notes,
            last_synced_at,
            created_at,
            updated_at
        FROM customers
        ORDER BY
            COALESCE(splynx_id::text, 'no_splynx_' || id::text),
            COALESCE(NULLIF(erpnext_id, ''), 'no_erpnext_' || id::text),
            updated_at DESC NULLS LAST,
            id DESC
    """)

    # Log duplicate customers that were de-duped
    op.execute("""
        INSERT INTO unified_contact_migration_log (source_table, source_id, conflict_type, conflict_value)
        SELECT 'customers', c.id, 'duplicate_external_id',
               CONCAT('splynx_id=', c.splynx_id, ', erpnext_id=', c.erpnext_id)
        FROM customers c
        WHERE c.id NOT IN (SELECT id FROM customer_staging)
    """)

    # =========================================================================
    # STEP 3: Migrate Customer data to unified_contacts (from staging)
    # =========================================================================
    op.execute("""
        INSERT INTO unified_contacts (
            contact_type,
            category,
            status,
            is_organization,
            name,
            company_name,
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
            splynx_id,
            erpnext_id,
            chatwoot_contact_id,
            zoho_id,
            legacy_customer_id,
            account_number,
            contract_number,
            vat_id,
            billing_type,
            mrr,
            blocking_date,
            days_until_blocking,
            deposit_balance,
            owner_id,
            pop_id,
            base_station,
            signup_date,
            activation_date,
            cancellation_date,
            churn_reason,
            contract_end_date,
            conversion_date,
            referrer,
            tags,
            notes,
            last_synced_at,
            created_at,
            updated_at
        )
        SELECT
            CASE
                WHEN status::text = 'prospect' THEN 'lead'::contacttype
                WHEN status::text = 'active' THEN 'customer'::contacttype
                WHEN status::text = 'inactive' THEN 'churned'::contacttype
                WHEN status::text = 'suspended' THEN 'customer'::contacttype
                ELSE 'lead'::contacttype
            END as contact_type,
            CASE
                WHEN customer_type = 'residential' THEN 'residential'::contactcategory
                WHEN customer_type = 'business' THEN 'business'::contactcategory
                WHEN customer_type = 'enterprise' THEN 'enterprise'::contactcategory
                ELSE 'residential'::contactcategory
            END as category,
            CASE
                WHEN status::text = 'active' THEN 'active'::contactstatus
                WHEN status::text = 'suspended' THEN 'suspended'::contactstatus
                ELSE 'inactive'::contactstatus
            END as status,
            -- B2C residential individuals are NOT organizations
            CASE
                WHEN customer_type = 'residential' THEN FALSE
                ELSE TRUE
            END as is_organization,
            name,
            CASE
                WHEN customer_type != 'residential' THEN name
                ELSE NULL
            END as company_name,
            NULLIF(TRIM(email), '') as email,
            NULLIF(TRIM(billing_email), '') as billing_email,
            NULLIF(TRIM(phone), '') as phone,
            NULLIF(TRIM(phone_secondary), '') as phone_secondary,
            address as address_line1,
            address_2 as address_line2,
            city,
            state,
            zip_code as postal_code,
            COALESCE(country, 'Nigeria') as country,
            latitude,
            longitude,
            gps as gps_raw,
            NULLIF(TRIM(splynx_id), '') as splynx_id,
            NULLIF(TRIM(erpnext_id), '') as erpnext_id,
            chatwoot_contact_id,
            NULLIF(TRIM(zoho_id), '') as zoho_id,
            id as legacy_customer_id,
            account_number,
            contract_number,
            vat_id,
            CASE
                WHEN billing_type = 'prepaid' THEN 'prepaid'::billingtype_uc
                WHEN billing_type = 'prepaid_monthly' THEN 'prepaid_monthly'::billingtype_uc
                WHEN billing_type = 'recurring' THEN 'recurring'::billingtype_uc
                ELSE NULL
            END as billing_type,
            mrr,
            blocking_date,
            days_until_blocking,
            deposit_balance,
            added_by_id as owner_id,
            pop_id,
            base_station,
            signup_date,
            activation_date,
            cancellation_date,
            NULL as churn_reason,
            contract_end_date,
            conversion_date,
            referrer,
            CASE WHEN labels IS NOT NULL AND labels != ''
                THEN to_jsonb(string_to_array(labels, ','))
                ELSE NULL
            END as tags,
            notes,
            last_synced_at,
            created_at,
            updated_at
        FROM customer_staging
        ON CONFLICT DO NOTHING
    """)

    # Update customers with their unified_contact_id
    op.execute("""
        UPDATE customers c
        SET unified_contact_id = uc.id
        FROM unified_contacts uc
        WHERE uc.legacy_customer_id = c.id
    """)

    # Log customers that failed to get unified_contact_id (collision victims)
    op.execute("""
        INSERT INTO unified_contact_migration_log (source_table, source_id, conflict_type, conflict_value)
        SELECT 'customers', c.id, 'no_unified_contact_created',
               CONCAT('name=', c.name, ', email=', c.email)
        FROM customers c
        WHERE c.unified_contact_id IS NULL
    """)

    # Link collision victims to existing unified contacts by external ID match
    op.execute("""
        UPDATE customers c
        SET unified_contact_id = (
            SELECT uc.id FROM unified_contacts uc
            WHERE (uc.splynx_id = c.splynx_id AND c.splynx_id IS NOT NULL AND c.splynx_id != '')
               OR (uc.erpnext_id = c.erpnext_id AND c.erpnext_id IS NOT NULL AND c.erpnext_id != '')
               OR (uc.email = c.email AND c.email IS NOT NULL AND c.email != '')
            LIMIT 1
        )
        WHERE c.unified_contact_id IS NULL
    """)

    op.execute("DROP TABLE IF EXISTS customer_staging")

    # =========================================================================
    # STEP 4: Create staging table for ERPNextLead data with de-duplication
    # Skip if erpnext_leads table doesn't exist
    # =========================================================================
    if table_exists('erpnext_leads'):
        op.execute("""
            CREATE TEMP TABLE lead_staging AS
            SELECT DISTINCT ON (COALESCE(NULLIF(name, ''), 'no_erpnext_' || id::text))
                id,
                name,
                status,
                lead_name,
                first_name,
                last_name,
                company_name,
                email_id,
                phone,
                mobile_no,
                city,
                state,
                country,
                source,
                campaign_name,
                industry,
                territory,
                notes,
                creation,
                modified
            FROM erpnext_leads
            ORDER BY
                COALESCE(NULLIF(name, ''), 'no_erpnext_' || id::text),
                modified DESC NULLS LAST,
                id DESC
        """)

        # Log duplicate leads
        op.execute("""
            INSERT INTO unified_contact_migration_log (source_table, source_id, conflict_type, conflict_value)
            SELECT 'erpnext_leads', l.id, 'duplicate_erpnext_id', l.name
            FROM erpnext_leads l
            WHERE l.id NOT IN (SELECT id FROM lead_staging)
        """)

        # =========================================================================
        # STEP 5: Migrate ERPNextLead data to unified_contacts
        # Skip leads that already exist (by email match from customers)
        # =========================================================================
        op.execute("""
            INSERT INTO unified_contacts (
                contact_type,
                category,
                status,
                is_organization,
                name,
                first_name,
                last_name,
                company_name,
                email,
                phone,
                mobile,
                city,
                state,
                country,
                erpnext_id,
                legacy_lead_id,
                source,
                source_campaign,
                industry,
                territory,
                notes,
                created_at,
                updated_at
            )
            SELECT
                'lead'::contacttype as contact_type,
                'residential'::contactcategory as category,
                CASE
                    WHEN status IN ('Converted', 'Do Not Contact') THEN 'inactive'::contactstatus
                    ELSE 'active'::contactstatus
                END as status,
                CASE
                    WHEN company_name IS NOT NULL AND company_name != '' THEN TRUE
                    ELSE FALSE
                END as is_organization,
                COALESCE(lead_name, CONCAT(first_name, ' ', last_name)) as name,
                first_name,
                last_name,
                NULLIF(TRIM(company_name), '') as company_name,
                NULLIF(TRIM(email_id), '') as email,
                NULLIF(TRIM(phone), '') as phone,
                NULLIF(TRIM(mobile_no), '') as mobile,
                city,
                state,
                COALESCE(country, 'Nigeria') as country,
                NULLIF(TRIM(name), '') as erpnext_id,
                id as legacy_lead_id,
                source,
                campaign_name as source_campaign,
                industry,
                territory,
                notes,
                creation as created_at,
                modified as updated_at
            FROM lead_staging ls
            WHERE NOT EXISTS (
                SELECT 1 FROM unified_contacts uc
                WHERE (uc.email = ls.email_id AND ls.email_id IS NOT NULL AND ls.email_id != '')
                   OR (uc.erpnext_id = ls.name AND ls.name IS NOT NULL AND ls.name != '')
            )
            ON CONFLICT DO NOTHING
        """)

        # Link leads to unified contacts
        op.execute("""
            WITH lead_links AS (
                SELECT l.id as lead_id, uc.id as uc_id
                FROM erpnext_leads l
                JOIN unified_contacts uc ON uc.legacy_lead_id = l.id
                UNION
                SELECT l.id as lead_id, uc.id as uc_id
                FROM erpnext_leads l
                JOIN unified_contacts uc ON (
                    (uc.erpnext_id = l.name AND l.name IS NOT NULL AND l.name != '')
                    OR (uc.email = l.email_id AND l.email_id IS NOT NULL AND l.email_id != '')
                )
                WHERE uc.legacy_lead_id IS NULL
            )
            UPDATE erpnext_leads l
            SET unified_contact_id = ll.uc_id
            FROM lead_links ll
            WHERE l.id = ll.lead_id
              AND l.unified_contact_id IS NULL
        """)

        op.execute("DROP TABLE IF EXISTS lead_staging")

    # =========================================================================
    # STEP 6: Migrate CRM Contact data to unified_contacts (as person type)
    # Only for contacts that have a parent org in unified_contacts
    # Skip if contacts table doesn't exist (CRM migration hasn't run yet)
    # =========================================================================
    if table_exists('contacts'):
        op.execute("""
        INSERT INTO unified_contacts (
            contact_type,
            category,
            status,
            is_organization,
            parent_id,
            is_primary_contact,
            is_billing_contact,
            is_decision_maker,
            name,
            first_name,
            last_name,
            email,
            phone,
            mobile,
            designation,
            department,
            linkedin_url,
            legacy_contact_id,
            notes,
            created_at,
            updated_at
        )
        SELECT
            'person'::contacttype as contact_type,
            'residential'::contactcategory as category,
            CASE WHEN is_active THEN 'active'::contactstatus ELSE 'inactive'::contactstatus END as status,
            FALSE as is_organization,
            (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_customer_id = c.customer_id LIMIT 1) as parent_id,
            is_primary as is_primary_contact,
            is_billing_contact,
            is_decision_maker,
            full_name as name,
            first_name,
            last_name,
            NULLIF(TRIM(email), '') as email,
            NULLIF(TRIM(phone), '') as phone,
            NULLIF(TRIM(mobile), '') as mobile,
            designation,
            department,
            linkedin_url,
            id as legacy_contact_id,
            notes,
            created_at,
            updated_at
        FROM contacts c
        WHERE customer_id IS NOT NULL
        AND EXISTS (SELECT 1 FROM unified_contacts uc WHERE uc.legacy_customer_id = c.customer_id)
        ON CONFLICT DO NOTHING
    """)

        # Also handle standalone CRM contacts (no parent org) - store as lead type
        op.execute("""
            INSERT INTO unified_contacts (
                contact_type,
                category,
                status,
                is_organization,
                name,
                first_name,
                last_name,
                email,
                phone,
                mobile,
                designation,
                department,
                linkedin_url,
                legacy_contact_id,
                notes,
                created_at,
                updated_at
            )
            SELECT
                'lead'::contacttype as contact_type,
                'residential'::contactcategory as category,
                CASE WHEN is_active THEN 'active'::contactstatus ELSE 'inactive'::contactstatus END as status,
                FALSE as is_organization,
                full_name as name,
                first_name,
                last_name,
                NULLIF(TRIM(email), '') as email,
                NULLIF(TRIM(phone), '') as phone,
                NULLIF(TRIM(mobile), '') as mobile,
                designation,
                department,
                linkedin_url,
                id as legacy_contact_id,
                notes,
                created_at,
                updated_at
            FROM contacts c
            WHERE (customer_id IS NULL OR NOT EXISTS (
                SELECT 1 FROM unified_contacts uc WHERE uc.legacy_customer_id = c.customer_id
            ))
            AND NOT EXISTS (
                SELECT 1 FROM unified_contacts uc WHERE uc.legacy_contact_id = c.id
            )
            AND NOT EXISTS (
                SELECT 1 FROM unified_contacts uc
                WHERE uc.email = c.email AND c.email IS NOT NULL AND c.email != ''
            )
            ON CONFLICT DO NOTHING
        """)

        # Update contacts with their unified_contact_id
        op.execute("""
            UPDATE contacts c
            SET unified_contact_id = COALESCE(
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_contact_id = c.id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.email = c.email AND c.email IS NOT NULL AND c.email != '' LIMIT 1)
            )
            WHERE c.unified_contact_id IS NULL
        """)

    # =========================================================================
    # STEP 7: Migrate InboxContact data to unified_contacts
    # (Only if not already migrated via Customer or other sources)
    # Skip if inbox_contacts table doesn't exist
    # =========================================================================
    if table_exists('inbox_contacts'):
        op.execute("""
            INSERT INTO unified_contacts (
            contact_type,
            category,
            status,
            is_organization,
            name,
            company_name,
            email,
            phone,
            designation,
            legacy_inbox_contact_id,
            tags,
            total_conversations,
            last_contact_date,
            created_at,
            updated_at
        )
        SELECT
            'lead'::contacttype as contact_type,
            'residential'::contactcategory as category,
            'active'::contactstatus as status,
            CASE
                WHEN company IS NOT NULL AND company != '' THEN TRUE
                ELSE FALSE
            END as is_organization,
            name,
            NULLIF(TRIM(company), '') as company_name,
            NULLIF(TRIM(email), '') as email,
            NULLIF(TRIM(phone), '') as phone,
            job_title as designation,
            id as legacy_inbox_contact_id,
            tags::jsonb as tags,
            total_conversations,
            last_contact_at as last_contact_date,
            created_at,
            updated_at
        FROM inbox_contacts ic
        WHERE NOT EXISTS (
            SELECT 1 FROM unified_contacts uc
            WHERE (uc.email = ic.email AND ic.email IS NOT NULL AND ic.email != '')
               OR uc.legacy_customer_id = ic.customer_id
               OR uc.legacy_inbox_contact_id = ic.id
        )
        ON CONFLICT DO NOTHING
        """)

        # Update inbox_contacts with their unified_contact_id
        op.execute("""
            UPDATE inbox_contacts ic
            SET unified_contact_id = COALESCE(
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_inbox_contact_id = ic.id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.email = ic.email AND ic.email IS NOT NULL AND ic.email != '' LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_customer_id = ic.customer_id AND ic.customer_id IS NOT NULL LIMIT 1)
            )
            WHERE ic.unified_contact_id IS NULL
        """)

    # =========================================================================
    # STEP 8: Link opportunities to unified_contacts
    # Skip if opportunities table doesn't exist
    # =========================================================================
    if table_exists('opportunities') and column_exists('opportunities', 'unified_contact_id'):
        op.execute("""
            UPDATE opportunities o
            SET unified_contact_id = COALESCE(
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_customer_id = o.customer_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_lead_id = o.lead_id LIMIT 1)
            )
            WHERE o.unified_contact_id IS NULL
        """)

    # =========================================================================
    # STEP 9: Link activities to unified_contacts
    # Skip if activities table doesn't exist
    # =========================================================================
    if table_exists('activities') and column_exists('activities', 'unified_contact_id'):
        op.execute("""
            UPDATE activities a
            SET unified_contact_id = COALESCE(
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_customer_id = a.customer_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_lead_id = a.lead_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_contact_id = a.contact_id LIMIT 1)
            )
            WHERE a.unified_contact_id IS NULL
        """)

    # =========================================================================
    # STEP 10: Link omni_conversations to unified_contacts
    # =========================================================================
    if table_exists('omni_conversations') and column_exists('omni_conversations', 'unified_contact_id'):
        op.execute("""
            UPDATE omni_conversations oc
            SET unified_contact_id = COALESCE(
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_customer_id = oc.customer_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_lead_id = oc.lead_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.email = oc.contact_email AND oc.contact_email IS NOT NULL LIMIT 1)
            )
            WHERE oc.unified_contact_id IS NULL
        """)

    # =========================================================================
    # STEP 11: Link omni_participants to unified_contacts
    # =========================================================================
    if table_exists('omni_participants') and column_exists('omni_participants', 'unified_contact_id'):
        op.execute("""
            UPDATE omni_participants op
            SET unified_contact_id = COALESCE(
                (SELECT uc.id FROM unified_contacts uc WHERE uc.legacy_customer_id = op.customer_id LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.email = op.handle AND op.channel_type = 'email' LIMIT 1),
                (SELECT uc.id FROM unified_contacts uc WHERE uc.phone = op.handle AND op.channel_type IN ('sms', 'whatsapp') LIMIT 1)
            )
            WHERE op.unified_contact_id IS NULL
        """)

    # =========================================================================
    # STEP 12: Update search vectors for all migrated contacts
    # =========================================================================
    op.execute("""
        UPDATE unified_contacts
        SET search_vector =
            setweight(to_tsvector('english', COALESCE(name, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(company_name, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(email, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(phone, '')), 'B') ||
            setweight(to_tsvector('english', COALESCE(city, '')), 'C') ||
            setweight(to_tsvector('english', COALESCE(account_number, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(notes, '')), 'D')
    """)

    # =========================================================================
    # STEP 13: Report migration statistics
    # Handle missing tables gracefully
    # =========================================================================
    stats_json = """
        json_build_object(
            'total_unified_contacts', (SELECT COUNT(*) FROM unified_contacts),
            'customers_linked', (SELECT COUNT(*) FROM customers WHERE unified_contact_id IS NOT NULL),
            'customers_orphaned', (SELECT COUNT(*) FROM customers WHERE unified_contact_id IS NULL),
            'leads_linked', COALESCE((SELECT COUNT(*) FROM erpnext_leads WHERE unified_contact_id IS NOT NULL), 0),
            'collisions_logged', (SELECT COUNT(*) FROM unified_contact_migration_log WHERE conflict_type != 'stats')
        )
    """
    # Add CRM contacts stat if table exists
    if table_exists('contacts') and column_exists('contacts', 'unified_contact_id'):
        stats_json = stats_json.replace(
            "'collisions_logged'",
            "'crm_contacts_linked', (SELECT COUNT(*) FROM contacts WHERE unified_contact_id IS NOT NULL), 'collisions_logged'"
        )
    # Add inbox contacts stat if table exists
    if table_exists('inbox_contacts') and column_exists('inbox_contacts', 'unified_contact_id'):
        stats_json = stats_json.replace(
            "'collisions_logged'",
            "'inbox_contacts_linked', (SELECT COUNT(*) FROM inbox_contacts WHERE unified_contact_id IS NOT NULL), 'collisions_logged'"
        )

    op.execute(f"""
        INSERT INTO unified_contact_migration_log (source_table, source_id, conflict_type, conflict_value)
        SELECT 'MIGRATION_SUMMARY', 0, 'stats', ({stats_json})::text
    """)


def downgrade() -> None:
    # Remove unified_contact_id columns from all tables (only if they exist)

    if table_exists('inbox_contacts') and column_exists('inbox_contacts', 'unified_contact_id'):
        op.drop_index('ix_inbox_contacts_unified_contact_id', table_name='inbox_contacts')
        op.drop_column('inbox_contacts', 'unified_contact_id')

    if table_exists('omni_participants') and column_exists('omni_participants', 'unified_contact_id'):
        op.drop_index('ix_omni_participants_unified_contact_id', table_name='omni_participants')
        op.drop_column('omni_participants', 'unified_contact_id')

    if table_exists('omni_conversations') and column_exists('omni_conversations', 'unified_contact_id'):
        op.drop_index('ix_omni_conversations_unified_contact_id', table_name='omni_conversations')
        op.drop_column('omni_conversations', 'unified_contact_id')

    if table_exists('contacts') and column_exists('contacts', 'unified_contact_id'):
        op.drop_index('ix_contacts_unified_contact_id', table_name='contacts')
        op.drop_column('contacts', 'unified_contact_id')

    if table_exists('activities') and column_exists('activities', 'unified_contact_id'):
        op.drop_index('ix_activities_unified_contact_id', table_name='activities')
        op.drop_column('activities', 'unified_contact_id')

    if table_exists('opportunities') and column_exists('opportunities', 'unified_contact_id'):
        op.drop_index('ix_opportunities_unified_contact_id', table_name='opportunities')
        op.drop_column('opportunities', 'unified_contact_id')

    if table_exists('customers') and column_exists('customers', 'unified_contact_id'):
        op.drop_index('ix_customers_unified_contact_id', table_name='customers')
        op.drop_column('customers', 'unified_contact_id')

    if table_exists('erpnext_leads') and column_exists('erpnext_leads', 'unified_contact_id'):
        op.drop_index('ix_erpnext_leads_unified_contact_id', table_name='erpnext_leads')
        op.drop_column('erpnext_leads', 'unified_contact_id')

    # Clear migrated data from unified_contacts
    if table_exists('unified_contacts'):
        op.execute("DELETE FROM unified_contacts WHERE legacy_customer_id IS NOT NULL")
        op.execute("DELETE FROM unified_contacts WHERE legacy_lead_id IS NOT NULL")
        op.execute("DELETE FROM unified_contacts WHERE legacy_contact_id IS NOT NULL")
        op.execute("DELETE FROM unified_contacts WHERE legacy_inbox_contact_id IS NOT NULL")

    # Drop migration log table
    op.execute("DROP TABLE IF EXISTS unified_contact_migration_log")
