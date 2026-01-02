"""Unified Identity Model - Party-based identity system.

Replaces: users, employees, customers, contacts, unified_contacts, leads, suppliers
with a single party-based identity model.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers
revision = "20260102_unified_identity"
down_revision = "chatwoot_metrics_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================
    # 0) Utility functions
    # ==========================================
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION normalize_email(text)
        RETURNS text AS $$
        BEGIN
            IF $1 IS NULL THEN RETURN NULL; END IF;
            RETURN lower(trim($1));
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION normalize_phone(text)
        RETURNS text AS $$
        BEGIN
            IF $1 IS NULL THEN RETURN NULL; END IF;
            RETURN regexp_replace($1, '\\s+', '', 'g');
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION ensure_party_type(party_id bigint, expected_type text)
        RETURNS void AS $$
        DECLARE
            actual text;
        BEGIN
            SELECT type INTO actual FROM parties WHERE id = party_id;
            IF actual IS NULL THEN
                RAISE EXCEPTION 'Party % not found', party_id;
            END IF;
            IF actual <> expected_type THEN
                RAISE EXCEPTION 'Party % type mismatch: expected %, got %', party_id, expected_type, actual;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # ==========================================
    # 1) parties - Canonical identity
    # ==========================================
    op.create_table(
        "parties",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("name", sa.Text()),
        sa.Column("first_name", sa.Text()),
        sa.Column("last_name", sa.Text()),
        sa.Column("legal_name", sa.Text()),
        sa.Column("trading_name", sa.Text()),
        sa.Column("primary_email", sa.Text()),
        sa.Column("primary_phone", sa.Text()),
        sa.Column("emails", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("phones", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("addresses", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("external_ids", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("timezone", sa.Text()),
        sa.Column("locale", sa.Text(), server_default="en"),
        sa.Column("tax_id", sa.Text()),
        sa.Column("tags", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("custom_fields", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("type IN ('person', 'organization')", name="ck_parties_type"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'blocked')", name="ck_parties_status"),
    )

    op.create_index(
        "uq_parties_primary_email",
        "parties",
        ["primary_email"],
        unique=True,
        postgresql_where=sa.text("primary_email IS NOT NULL"),
    )
    op.create_index(
        "uq_parties_primary_phone",
        "parties",
        ["primary_phone"],
        unique=True,
        postgresql_where=sa.text("primary_phone IS NOT NULL"),
    )
    op.create_index("ix_parties_type_status", "parties", ["type", "status"])
    op.create_index("ix_parties_name", "parties", ["name"])

    # Trigger: sync primary email/phone from JSONB
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_party_primary_contact()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.primary_email := (
                SELECT normalize_email(e->>'address')
                FROM jsonb_array_elements(COALESCE(NEW.emails, '[]'::jsonb)) e
                WHERE (e->>'is_primary')::boolean = true
                LIMIT 1
            );
            IF NEW.primary_email IS NULL AND jsonb_array_length(COALESCE(NEW.emails, '[]'::jsonb)) > 0 THEN
                NEW.primary_email := normalize_email(NEW.emails->0->>'address');
            END IF;

            NEW.primary_phone := (
                SELECT normalize_phone(p->>'number')
                FROM jsonb_array_elements(COALESCE(NEW.phones, '[]'::jsonb)) p
                WHERE (p->>'is_primary')::boolean = true
                LIMIT 1
            );
            IF NEW.primary_phone IS NULL AND jsonb_array_length(COALESCE(NEW.phones, '[]'::jsonb)) > 0 THEN
                NEW.primary_phone := normalize_phone(NEW.phones->0->>'number');
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_parties_updated_at
            BEFORE UPDATE ON parties
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();

        CREATE TRIGGER trg_parties_sync_contact
            BEFORE INSERT OR UPDATE OF emails, phones ON parties
            FOR EACH ROW EXECUTE FUNCTION sync_party_primary_contact();
        """
    )

    # ==========================================
    # 2) ref_party_role_types - Reference table
    # ==========================================
    op.create_table(
        "ref_party_role_types",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
    )

    # Seed data for party role types
    op.execute(
        """
        INSERT INTO ref_party_role_types (code, label, category, description, sort_order) VALUES
        -- CRM roles
        ('lead', 'Lead', 'crm', 'Unqualified prospect', 10),
        ('prospect', 'Prospect', 'crm', 'Qualified lead in sales pipeline', 20),
        ('customer', 'Customer', 'crm', 'Active paying customer', 30),
        ('churned', 'Churned', 'crm', 'Former customer', 40),

        -- Business relationships
        ('vendor', 'Vendor', 'business', 'Supplier of goods/services', 100),
        ('supplier', 'Supplier', 'business', 'Alternative term for vendor', 101),
        ('reseller', 'Reseller', 'business', 'Sells your products/services', 110),
        ('partner', 'Partner', 'business', 'Strategic business partner', 120),
        ('affiliate', 'Affiliate', 'business', 'Referral/commission partner', 130),
        ('distributor', 'Distributor', 'business', 'Wholesale distribution partner', 140),

        -- Internal roles
        ('employee', 'Employee', 'internal', 'Full-time or part-time employee', 200),
        ('contractor', 'Contractor', 'internal', 'Independent contractor', 210),
        ('intern', 'Intern', 'internal', 'Internship position', 220),

        -- System access roles
        ('user', 'User', 'system', 'Has login access to the system', 300),
        ('admin', 'Admin', 'system', 'System administrator', 310),
        ('support_agent', 'Support Agent', 'system', 'Customer support staff', 320),
        ('sales_rep', 'Sales Rep', 'system', 'Sales representative', 330),
        ('account_manager', 'Account Manager', 'system', 'Manages customer accounts', 340);
        """
    )

    # ==========================================
    # 3) party_roles - What a party is to you
    # ==========================================
    op.create_table(
        "party_roles",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), sa.ForeignKey("ref_party_role_types.code"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("scope_party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="SET NULL")),
        sa.Column("since", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("until", sa.DateTime(timezone=True)),
        # CRM fields
        sa.Column("source", sa.Text()),
        sa.Column("source_campaign", sa.Text()),
        sa.Column("qualification", sa.Text()),
        sa.Column("lead_score", sa.Integer()),
        # Assignment
        sa.Column("owner_party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="SET NULL")),
        # Vendor fields
        sa.Column("payment_terms", sa.Text()),
        sa.Column("credit_limit", sa.Numeric(18, 2)),
        # Metadata
        sa.Column("notes", sa.Text()),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'inactive', 'suspended')", name="ck_party_roles_status"),
    )

    op.create_index(
        "uq_party_roles_active",
        "party_roles",
        ["party_id", "role", "scope_party_id"],
        unique=True,
        postgresql_where=sa.text("until IS NULL"),
    )
    op.create_index("ix_party_roles_role_status", "party_roles", ["role", "status"])
    op.create_index("ix_party_roles_party", "party_roles", ["party_id"])

    op.execute(
        """
        CREATE TRIGGER trg_party_roles_updated_at
            BEFORE UPDATE ON party_roles
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """
    )

    # ==========================================
    # 4) ref_relation_types - Reference table
    # ==========================================
    op.create_table(
        "ref_relation_types",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("from_type", sa.Text(), nullable=False),
        sa.Column("to_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.CheckConstraint("from_type IN ('person', 'organization', 'any')", name="ck_ref_relation_from_type"),
        sa.CheckConstraint("to_type IN ('person', 'organization', 'any')", name="ck_ref_relation_to_type"),
    )

    # Seed data for relation types
    op.execute(
        """
        INSERT INTO ref_relation_types (code, label, from_type, to_type, description, sort_order) VALUES
        -- Person -> Organization
        ('employee_of', 'Employee Of', 'person', 'organization', 'Employment relationship', 10),
        ('contractor_to', 'Contractor To', 'person', 'organization', 'Contractor engagement', 20),
        ('owner_of', 'Owner Of', 'person', 'organization', 'Ownership stake', 30),
        ('director_of', 'Director Of', 'person', 'organization', 'Board director', 40),
        ('member_of', 'Member Of', 'person', 'organization', 'Membership', 50),
        ('agent_for', 'Agent For', 'person', 'organization', 'Acting as agent', 60),
        ('representative_of', 'Representative Of', 'person', 'organization', 'Sales/business representative', 70),
        ('founder_of', 'Founder Of', 'person', 'organization', 'Company founder', 80),

        -- Organization -> Organization
        ('subsidiary_of', 'Subsidiary Of', 'organization', 'organization', 'Subsidiary company', 100),
        ('parent_of', 'Parent Of', 'organization', 'organization', 'Parent company', 110),
        ('franchise_of', 'Franchise Of', 'organization', 'organization', 'Franchise relationship', 120),
        ('partner_with', 'Partner With', 'organization', 'organization', 'Business partnership', 130),
        ('supplier_to', 'Supplier To', 'organization', 'organization', 'Supplier relationship', 140),
        ('distributor_for', 'Distributor For', 'organization', 'organization', 'Distribution agreement', 150),

        -- Person -> Person
        ('referred_by', 'Referred By', 'person', 'person', 'Referral source', 200),
        ('reports_to', 'Reports To', 'person', 'person', 'Management hierarchy', 210),
        ('mentored_by', 'Mentored By', 'person', 'person', 'Mentorship', 220),
        ('spouse_of', 'Spouse Of', 'person', 'person', 'Spouse (for residential accounts)', 230),

        -- Any -> Any
        ('related_to', 'Related To', 'any', 'any', 'General relationship', 300);
        """
    )

    # ==========================================
    # 5) party_relations - Generic relationships
    # ==========================================
    op.create_table(
        "party_relations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("from_party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.Text(), sa.ForeignKey("ref_relation_types.code"), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("department", sa.Text()),
        sa.Column("since", sa.DateTime(timezone=True)),
        sa.Column("until", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_party_relations_from_to", "party_relations", ["from_party_id", "to_party_id"])
    op.create_index(
        "uq_party_relations_active",
        "party_relations",
        ["from_party_id", "to_party_id", "relation_type"],
        unique=True,
        postgresql_where=sa.text("until IS NULL"),
    )
    op.create_index("ix_party_relations_to", "party_relations", ["to_party_id"])

    # Trigger: enforce relation type constraints
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_relation_types()
        RETURNS TRIGGER AS $$
        DECLARE
            from_t text;
            to_t text;
            rule record;
        BEGIN
            SELECT type INTO from_t FROM parties WHERE id = NEW.from_party_id;
            SELECT type INTO to_t FROM parties WHERE id = NEW.to_party_id;
            SELECT * INTO rule FROM ref_relation_types WHERE code = NEW.relation_type;

            IF rule.from_type <> 'any' AND rule.from_type <> from_t THEN
                RAISE EXCEPTION 'Relation type % requires from_type %, got %', NEW.relation_type, rule.from_type, from_t;
            END IF;

            IF rule.to_type <> 'any' AND rule.to_type <> to_t THEN
                RAISE EXCEPTION 'Relation type % requires to_type %, got %', NEW.relation_type, rule.to_type, to_t;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_party_relations_validate
            BEFORE INSERT OR UPDATE ON party_relations
            FOR EACH ROW EXECUTE FUNCTION enforce_relation_types();
        """
    )

    # ==========================================
    # 6) customer_accounts - Billing entity
    # ==========================================
    op.create_table(
        "customer_accounts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_number", sa.Text(), nullable=False, unique=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("tier", sa.Text(), nullable=False, server_default="standard"),
        sa.Column("parent_account_id", sa.BigInteger(), sa.ForeignKey("customer_accounts.id", ondelete="SET NULL")),
        sa.Column("account_type", sa.Text(), nullable=False, server_default="direct"),
        # Billing
        sa.Column("billing_type", sa.Text()),
        sa.Column("billing_email", sa.Text()),
        sa.Column("billing_cycle", sa.Text()),
        sa.Column("payment_terms", sa.Text()),
        sa.Column("credit_limit", sa.Numeric(18, 2)),
        sa.Column("currency", sa.Text(), server_default="NGN"),
        # Financials
        sa.Column("mrr", sa.Numeric(18, 2)),
        sa.Column("total_revenue", sa.Numeric(18, 2)),
        sa.Column("outstanding_balance", sa.Numeric(18, 2)),
        # External
        sa.Column("external_ids", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("suspended_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'cancelled', 'pending')",
            name="ck_customer_accounts_status",
        ),
        sa.CheckConstraint("tier IN ('standard', 'premium', 'enterprise')", name="ck_customer_accounts_tier"),
        sa.CheckConstraint(
            "account_type IN ('direct', 'reseller_managed', 'sub_account')",
            name="ck_customer_accounts_type",
        ),
    )

    op.create_index("ix_customer_accounts_party", "customer_accounts", ["party_id"])
    op.create_index("ix_customer_accounts_status", "customer_accounts", ["status"])
    op.create_index("ix_customer_accounts_parent", "customer_accounts", ["parent_account_id"])

    # ==========================================
    # 7) customer_account_contacts - External contacts
    # ==========================================
    op.create_table(
        "customer_account_contacts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("person_party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("receives_invoices", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("receives_notifications", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("can_manage", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("since", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("until", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "role IN ('primary', 'billing', 'technical', 'decision_maker', 'other')",
            name="ck_customer_account_contacts_role",
        ),
    )

    op.create_index(
        "ix_customer_account_contacts_account_role",
        "customer_account_contacts",
        ["account_id", "role"],
    )
    op.create_index(
        "uq_customer_account_contacts_primary",
        "customer_account_contacts",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true AND until IS NULL"),
    )
    op.create_index(
        "ix_customer_account_contacts_person",
        "customer_account_contacts",
        ["person_party_id"],
    )

    # Type check trigger
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_account_contacts_types()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM ensure_party_type(NEW.person_party_id, 'person');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_account_contacts_type_check
            BEFORE INSERT OR UPDATE ON customer_account_contacts
            FOR EACH ROW EXECUTE FUNCTION trg_account_contacts_types();
        """
    )

    # ==========================================
    # 8) customer_account_team - Internal staff
    # ==========================================
    op.create_table(
        "customer_account_team",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("person_party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("since", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("until", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "role IN ('sales_rep', 'account_manager', 'support_agent', 'technical_lead')",
            name="ck_customer_account_team_role",
        ),
    )

    op.create_index(
        "ix_customer_account_team_account_role",
        "customer_account_team",
        ["account_id", "role"],
    )
    op.create_index("ix_customer_account_team_person", "customer_account_team", ["person_party_id"])

    # Type check trigger
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_account_team_types()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM ensure_party_type(NEW.person_party_id, 'person');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_account_team_type_check
            BEFORE INSERT OR UPDATE ON customer_account_team
            FOR EACH ROW EXECUTE FUNCTION trg_account_team_types();
        """
    )

    # ==========================================
    # 9) customer_account_resellers - Reseller linkage
    # ==========================================
    op.create_table(
        "customer_account_resellers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reseller_party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("commission_rate", sa.Numeric(5, 2)),
        sa.Column("since", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("until", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
    )

    op.create_index(
        "uq_customer_account_resellers_active",
        "customer_account_resellers",
        ["account_id", "reseller_party_id"],
        unique=True,
        postgresql_where=sa.text("until IS NULL"),
    )
    op.create_index(
        "ix_customer_account_resellers_reseller",
        "customer_account_resellers",
        ["reseller_party_id"],
    )

    # Type check trigger (reseller must be organization)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_account_resellers_types()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM ensure_party_type(NEW.reseller_party_id, 'organization');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_account_resellers_type_check
            BEFORE INSERT OR UPDATE ON customer_account_resellers
            FOR EACH ROW EXECUTE FUNCTION trg_account_resellers_types();
        """
    )

    # ==========================================
    # 10) party_external_ids - Identity mapping
    # ==========================================
    op.create_table(
        "party_external_ids",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("external_key_type", sa.Text()),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("system", "external_id", name="uq_party_external_ids_system_extid"),
    )

    op.create_index("ix_party_external_ids_party", "party_external_ids", ["party_id"])
    op.create_index("ix_party_external_ids_system", "party_external_ids", ["system"])
    op.create_index("ix_party_external_ids_lookup", "party_external_ids", ["system", "external_id"])

    op.execute(
        """
        CREATE TRIGGER trg_party_external_ids_updated_at
            BEFORE UPDATE ON party_external_ids
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """
    )

    # ==========================================
    # 11) credentials - Authentication
    # ==========================================
    op.create_table(
        "credentials",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text()),
        sa.Column("secret_hash", sa.Text()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("mfa_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "type IN ('password', 'oauth', 'sso', 'api_key', 'magic_link')",
            name="ck_credentials_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled', 'expired', 'locked')",
            name="ck_credentials_status",
        ),
        sa.CheckConstraint(
            "(type IN ('oauth', 'sso') AND provider IS NOT NULL) OR (type IN ('password', 'api_key', 'magic_link'))",
            name="ck_credentials_provider",
        ),
    )

    op.execute(
        """
        CREATE UNIQUE INDEX uq_credentials_type_provider_identifier
        ON credentials (type, COALESCE(provider, ''), identifier);
        """
    )
    op.create_index("ix_credentials_party", "credentials", ["party_id"])
    op.create_index("ix_credentials_identifier", "credentials", ["identifier"])

    op.execute(
        """
        CREATE TRIGGER trg_credentials_updated_at
            BEFORE UPDATE ON credentials
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """
    )

    # ==========================================
    # 12) memberships - Workspace access
    # ==========================================
    op.create_table(
        "memberships",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("org_party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_party_id", sa.BigInteger(), sa.ForeignKey("parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("permissions", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("invited_at", sa.DateTime(timezone=True)),
        sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("suspended_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "access_role IN ('owner', 'admin', 'manager', 'member', 'support', 'viewer')",
            name="ck_memberships_access_role",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'invited', 'suspended', 'removed')",
            name="ck_memberships_status",
        ),
    )

    op.create_index("uq_memberships_org_person", "memberships", ["org_party_id", "person_party_id"], unique=True)
    op.create_index("ix_memberships_person_status", "memberships", ["person_party_id", "status"])

    # Type check trigger
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_memberships_types()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM ensure_party_type(NEW.org_party_id, 'organization');
            PERFORM ensure_party_type(NEW.person_party_id, 'person');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_memberships_type_check
            BEFORE INSERT OR UPDATE ON memberships
            FOR EACH ROW EXECUTE FUNCTION trg_memberships_types();
        """
    )


def downgrade() -> None:
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS trg_memberships_type_check ON memberships;")
    op.execute("DROP TRIGGER IF EXISTS trg_credentials_updated_at ON credentials;")
    op.execute("DROP TRIGGER IF EXISTS trg_party_external_ids_updated_at ON party_external_ids;")
    op.execute("DROP TRIGGER IF EXISTS trg_account_resellers_type_check ON customer_account_resellers;")
    op.execute("DROP TRIGGER IF EXISTS trg_account_team_type_check ON customer_account_team;")
    op.execute("DROP TRIGGER IF EXISTS trg_account_contacts_type_check ON customer_account_contacts;")
    op.execute("DROP TRIGGER IF EXISTS trg_party_relations_validate ON party_relations;")
    op.execute("DROP TRIGGER IF EXISTS trg_party_roles_updated_at ON party_roles;")
    op.execute("DROP TRIGGER IF EXISTS trg_parties_sync_contact ON parties;")
    op.execute("DROP TRIGGER IF EXISTS trg_parties_updated_at ON parties;")

    # Drop tables in reverse order
    op.drop_table("memberships")
    op.drop_table("credentials")
    op.drop_table("party_external_ids")
    op.drop_table("customer_account_resellers")
    op.drop_table("customer_account_team")
    op.drop_table("customer_account_contacts")
    op.drop_table("customer_accounts")
    op.drop_table("party_relations")
    op.drop_table("ref_relation_types")
    op.drop_table("party_roles")
    op.drop_table("ref_party_role_types")
    op.drop_table("parties")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS trg_memberships_types() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS trg_account_resellers_types() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS trg_account_team_types() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS trg_account_contacts_types() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS enforce_relation_types() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS sync_party_primary_contact() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS ensure_party_type(bigint, text) CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS normalize_phone(text) CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS normalize_email(text) CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at() CASCADE;")
