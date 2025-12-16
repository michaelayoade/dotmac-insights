"""Add unified contact model

Consolidates Customer, ERPNextLead, Contact (CRM), and InboxContact into
a single unified_contacts table.

Revision ID: uc001_unified_contact
Revises: fs002_fulltext_search
Create Date: 2025-12-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'uc001_unified_contact'
down_revision = 'fs002_fulltext_search'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums using raw SQL with IF NOT EXISTS
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contacttype') THEN
                CREATE TYPE contacttype AS ENUM ('lead', 'prospect', 'customer', 'churned', 'person');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contactcategory') THEN
                CREATE TYPE contactcategory AS ENUM ('residential', 'business', 'enterprise', 'government', 'non_profit');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contactstatus') THEN
                CREATE TYPE contactstatus AS ENUM ('active', 'inactive', 'suspended', 'do_not_contact');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'billingtype_uc') THEN
                CREATE TYPE billingtype_uc AS ENUM ('prepaid', 'prepaid_monthly', 'recurring', 'one_time');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'leadqualification') THEN
                CREATE TYPE leadqualification AS ENUM ('unqualified', 'cold', 'warm', 'hot', 'qualified');
            END IF;
        END
        $$;
    """)

    # Create unified_contacts table using postgresql.ENUM with create_type=False
    contact_type_enum = postgresql.ENUM('lead', 'prospect', 'customer', 'churned', 'person', name='contacttype', create_type=False)
    contact_category_enum = postgresql.ENUM('residential', 'business', 'enterprise', 'government', 'non_profit', name='contactcategory', create_type=False)
    contact_status_enum = postgresql.ENUM('active', 'inactive', 'suspended', 'do_not_contact', name='contactstatus', create_type=False)
    billing_type_enum = postgresql.ENUM('prepaid', 'prepaid_monthly', 'recurring', 'one_time', name='billingtype_uc', create_type=False)
    lead_qual_enum = postgresql.ENUM('unqualified', 'cold', 'warm', 'hot', 'qualified', name='leadqualification', create_type=False)

    op.create_table(
        'unified_contacts',

        # Primary key
        sa.Column('id', sa.Integer(), nullable=False),

        # Type & Classification
        sa.Column('contact_type', contact_type_enum, nullable=False, server_default='lead'),
        sa.Column('category', contact_category_enum, nullable=False, server_default='residential'),
        sa.Column('status', contact_status_enum, nullable=False, server_default='active'),

        # Hierarchy
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('is_organization', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_primary_contact', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_billing_contact', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_decision_maker', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('designation', sa.String(100), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),

        # Basic Info
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('company_name', sa.String(255), nullable=True),

        # Contact Details
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('email_secondary', sa.String(255), nullable=True),
        sa.Column('billing_email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('phone_secondary', sa.String(50), nullable=True),
        sa.Column('mobile', sa.String(50), nullable=True),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('linkedin_url', sa.String(255), nullable=True),

        # Address
        sa.Column('address_line1', sa.Text(), nullable=True),
        sa.Column('address_line2', sa.Text(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('country', sa.String(100), nullable=True, server_default='Nigeria'),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('gps_raw', sa.String(255), nullable=True),

        # External System IDs
        sa.Column('splynx_id', sa.Integer(), nullable=True),
        sa.Column('erpnext_id', sa.String(255), nullable=True),
        sa.Column('chatwoot_contact_id', sa.Integer(), nullable=True),
        sa.Column('zoho_id', sa.String(100), nullable=True),

        # Legacy IDs for migration
        sa.Column('legacy_customer_id', sa.Integer(), nullable=True),
        sa.Column('legacy_lead_id', sa.Integer(), nullable=True),
        sa.Column('legacy_contact_id', sa.Integer(), nullable=True),
        sa.Column('legacy_inbox_contact_id', sa.Integer(), nullable=True),

        # Account/Billing Info
        sa.Column('account_number', sa.String(100), nullable=True),
        sa.Column('contract_number', sa.String(100), nullable=True),
        sa.Column('vat_id', sa.String(100), nullable=True),
        sa.Column('billing_type', billing_type_enum, nullable=True),
        sa.Column('mrr', sa.Numeric(18, 2), nullable=True),
        sa.Column('total_revenue', sa.Numeric(18, 2), nullable=True),
        sa.Column('outstanding_balance', sa.Numeric(18, 2), nullable=True),
        sa.Column('credit_limit', sa.Numeric(18, 2), nullable=True),
        sa.Column('blocking_date', sa.DateTime(), nullable=True),
        sa.Column('days_until_blocking', sa.Integer(), nullable=True),
        sa.Column('deposit_balance', sa.Numeric(18, 2), nullable=True),

        # Lead/Sales Info
        sa.Column('lead_qualification', lead_qual_enum, nullable=True),
        sa.Column('lead_score', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(255), nullable=True),
        sa.Column('source_campaign', sa.String(255), nullable=True),
        sa.Column('referrer', sa.String(255), nullable=True),
        sa.Column('industry', sa.String(255), nullable=True),
        sa.Column('market_segment', sa.String(255), nullable=True),
        sa.Column('territory', sa.String(255), nullable=True),

        # Ownership & Assignment
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('sales_person', sa.String(255), nullable=True),
        sa.Column('account_manager', sa.String(255), nullable=True),
        sa.Column('pop_id', sa.Integer(), nullable=True),
        sa.Column('base_station', sa.String(255), nullable=True),

        # Lifecycle Dates
        sa.Column('first_contact_date', sa.DateTime(), nullable=True),
        sa.Column('last_contact_date', sa.DateTime(), nullable=True),
        sa.Column('qualified_date', sa.DateTime(), nullable=True),
        sa.Column('conversion_date', sa.DateTime(), nullable=True),
        sa.Column('signup_date', sa.DateTime(), nullable=True),
        sa.Column('activation_date', sa.DateTime(), nullable=True),
        sa.Column('contract_start_date', sa.Date(), nullable=True),
        sa.Column('contract_end_date', sa.Date(), nullable=True),
        sa.Column('cancellation_date', sa.DateTime(), nullable=True),
        sa.Column('churn_reason', sa.String(255), nullable=True),

        # Communication Preferences
        sa.Column('email_opt_in', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sms_opt_in', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('whatsapp_opt_in', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('phone_opt_in', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('preferred_language', sa.String(10), nullable=True, server_default='en'),
        sa.Column('preferred_channel', sa.String(50), nullable=True),

        # Tags & Metadata
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('custom_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),

        # Stats
        sa.Column('total_conversations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tickets', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_orders', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_invoices', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('nps_score', sa.Integer(), nullable=True),
        sa.Column('satisfaction_score', sa.Float(), nullable=True),

        # Sync & Audit
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_id'], ['unified_contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['owner_id'], ['employees.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['pop_id'], ['pops.id'], ondelete='SET NULL'),
        sa.CheckConstraint("(contact_type != 'person') OR (parent_id IS NOT NULL)", name='ck_person_has_parent'),
    )

    # Create indexes
    op.create_index('ix_unified_contacts_id', 'unified_contacts', ['id'])
    op.create_index('ix_unified_contacts_contact_type', 'unified_contacts', ['contact_type'])
    op.create_index('ix_unified_contacts_status', 'unified_contacts', ['status'])
    op.create_index('ix_unified_contacts_parent_id', 'unified_contacts', ['parent_id'])
    op.create_index('ix_unified_contacts_is_organization', 'unified_contacts', ['is_organization'])
    op.create_index('ix_unified_contacts_name', 'unified_contacts', ['name'])
    op.create_index('ix_unified_contacts_company_name', 'unified_contacts', ['company_name'])
    op.create_index('ix_unified_contacts_email', 'unified_contacts', ['email'])
    op.create_index('ix_unified_contacts_phone', 'unified_contacts', ['phone'])
    op.create_index('ix_unified_contacts_city', 'unified_contacts', ['city'])
    op.create_index('ix_unified_contacts_state', 'unified_contacts', ['state'])
    op.create_index('ix_unified_contacts_latitude', 'unified_contacts', ['latitude'])
    op.create_index('ix_unified_contacts_longitude', 'unified_contacts', ['longitude'])
    op.create_index('ix_unified_contacts_splynx_id', 'unified_contacts', ['splynx_id'], unique=True)
    op.create_index('ix_unified_contacts_erpnext_id', 'unified_contacts', ['erpnext_id'], unique=True)
    op.create_index('ix_unified_contacts_chatwoot_contact_id', 'unified_contacts', ['chatwoot_contact_id'])
    op.create_index('ix_unified_contacts_zoho_id', 'unified_contacts', ['zoho_id'])
    op.create_index('ix_unified_contacts_legacy_customer_id', 'unified_contacts', ['legacy_customer_id'])
    op.create_index('ix_unified_contacts_legacy_lead_id', 'unified_contacts', ['legacy_lead_id'])
    op.create_index('ix_unified_contacts_legacy_contact_id', 'unified_contacts', ['legacy_contact_id'])
    op.create_index('ix_unified_contacts_account_number', 'unified_contacts', ['account_number'], unique=True)
    op.create_index('ix_unified_contacts_owner_id', 'unified_contacts', ['owner_id'])
    op.create_index('ix_unified_contacts_territory', 'unified_contacts', ['territory'])
    op.create_index('ix_unified_contacts_source', 'unified_contacts', ['source'])
    op.create_index('ix_unified_contacts_base_station', 'unified_contacts', ['base_station'])
    op.create_index('ix_unified_contacts_last_contact_date', 'unified_contacts', ['last_contact_date'])
    op.create_index('ix_unified_contacts_created_at', 'unified_contacts', ['created_at'])

    # Composite indexes for common queries
    op.create_index('ix_unified_contacts_type_status', 'unified_contacts', ['contact_type', 'status'])
    op.create_index('ix_unified_contacts_email_type', 'unified_contacts', ['email', 'contact_type'])
    op.create_index('ix_unified_contacts_phone_type', 'unified_contacts', ['phone', 'contact_type'])
    op.create_index('ix_unified_contacts_owner_type', 'unified_contacts', ['owner_id', 'contact_type'])

    # Full-text search vector
    op.execute("""
        ALTER TABLE unified_contacts
        ADD COLUMN IF NOT EXISTS search_vector tsvector;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_unified_contacts_search_vector
        ON unified_contacts USING GIN(search_vector);
    """)

    # Create function to update search vector
    op.execute("""
        CREATE OR REPLACE FUNCTION unified_contacts_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', COALESCE(NEW.name, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.company_name, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.email, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.phone, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.city, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.account_number, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.notes, '')), 'D');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger
    op.execute("""
        DROP TRIGGER IF EXISTS unified_contacts_search_vector_trigger ON unified_contacts;
        CREATE TRIGGER unified_contacts_search_vector_trigger
        BEFORE INSERT OR UPDATE ON unified_contacts
        FOR EACH ROW
        EXECUTE FUNCTION unified_contacts_search_vector_update();
    """)


def downgrade() -> None:
    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS unified_contacts_search_vector_trigger ON unified_contacts;")
    op.execute("DROP FUNCTION IF EXISTS unified_contacts_search_vector_update();")

    # Drop table
    op.drop_table('unified_contacts')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS contacttype;")
    op.execute("DROP TYPE IF EXISTS contactcategory;")
    op.execute("DROP TYPE IF EXISTS contactstatus;")
    op.execute("DROP TYPE IF EXISTS billingtype_uc;")
    op.execute("DROP TYPE IF EXISTS leadqualification;")
