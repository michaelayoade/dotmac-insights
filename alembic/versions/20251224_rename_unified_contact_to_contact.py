"""Rename unified_contacts to contacts and add contact_id FKs

Revision ID: 20251224_rename_unified_contact_to_contact
Revises: 20251223_add_project_pm_features
Create Date: 2025-12-24

Changes:
- Rename unified_contacts table to contacts
- Drop ISP-specific columns (splynx_id, pop_id, base_station, etc.)
- Add contact_id FK to invoices, payments, credit_notes tables
- Update search vector trigger for new table name
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251224_rename_unified_contact_to_contact"
down_revision: Union[str, None] = "20251224_add_sync_schedules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # STEP 1: Drop ISP-specific indexes before dropping columns
    # =========================================================================
    op.execute("DROP INDEX IF EXISTS ix_unified_contacts_splynx_id;")
    op.execute("DROP INDEX IF EXISTS ix_unified_contacts_chatwoot_contact_id;")
    op.execute("DROP INDEX IF EXISTS ix_unified_contacts_base_station;")

    # =========================================================================
    # STEP 2: Drop the trigger and function (will recreate with new name)
    # =========================================================================
    op.execute("DROP TRIGGER IF EXISTS unified_contacts_search_vector_trigger ON unified_contacts;")
    op.execute("DROP FUNCTION IF EXISTS unified_contacts_search_vector_update();")

    # =========================================================================
    # STEP 3: Drop ISP-specific columns
    # =========================================================================
    columns_to_drop = [
        'splynx_id',
        'chatwoot_contact_id',
        'pop_id',
        'base_station',
        'blocking_date',
        'days_until_blocking',
        'legacy_inbox_contact_id',
    ]

    for col in columns_to_drop:
        op.execute(f"ALTER TABLE unified_contacts DROP COLUMN IF EXISTS {col};")

    # Drop pop_id foreign key constraint if exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'unified_contacts_pop_id_fkey'
            ) THEN
                ALTER TABLE unified_contacts DROP CONSTRAINT unified_contacts_pop_id_fkey;
            END IF;
        END $$;
    """)

    # =========================================================================
    # STEP 4: Ensure legacy contacts table doesn't block rename
    # =========================================================================
    op.execute("""
        DO $$
        DECLARE
            legacy_name text := 'crm_contacts_legacy';
            idx int := 0;
            r record;
            schema_name text;
        BEGIN
            SELECT n.nspname
            INTO schema_name
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = 'unified_contacts'
            LIMIT 1;

            IF schema_name IS NULL THEN
                schema_name := current_schema();
            END IF;

            IF to_regclass(format('%I.contacts', schema_name)) IS NOT NULL THEN
                WHILE to_regclass(format('%I.%I', schema_name, legacy_name)) IS NOT NULL LOOP
                    idx := idx + 1;
                    legacy_name := 'crm_contacts_legacy_' || idx;
                END LOOP;

                EXECUTE format('ALTER TABLE %I.contacts RENAME TO %I', schema_name, legacy_name);

                -- Rename indexes on legacy contacts to avoid name collisions
                FOR r IN
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = schema_name AND tablename = legacy_name
                LOOP
                    EXECUTE format(
                        'ALTER INDEX %I.%I RENAME TO %I',
                        schema_name,
                        r.indexname,
                        legacy_name || '_' || r.indexname
                    );
                END LOOP;
            END IF;
        END $$;
    """)

    # =========================================================================
    # STEP 5: Rename table from unified_contacts to contacts
    # =========================================================================
    op.rename_table('unified_contacts', 'contacts')

    # =========================================================================
    # STEP 6: Rename indexes to match new table name
    # =========================================================================
    index_renames = [
        ('ix_unified_contacts_id', 'ix_contacts_id'),
        ('ix_unified_contacts_contact_type', 'ix_contacts_contact_type'),
        ('ix_unified_contacts_status', 'ix_contacts_status'),
        ('ix_unified_contacts_parent_id', 'ix_contacts_parent_id'),
        ('ix_unified_contacts_is_organization', 'ix_contacts_is_organization'),
        ('ix_unified_contacts_name', 'ix_contacts_name'),
        ('ix_unified_contacts_company_name', 'ix_contacts_company_name'),
        ('ix_unified_contacts_email', 'ix_contacts_email'),
        ('ix_unified_contacts_phone', 'ix_contacts_phone'),
        ('ix_unified_contacts_city', 'ix_contacts_city'),
        ('ix_unified_contacts_state', 'ix_contacts_state'),
        ('ix_unified_contacts_latitude', 'ix_contacts_latitude'),
        ('ix_unified_contacts_longitude', 'ix_contacts_longitude'),
        ('ix_unified_contacts_erpnext_id', 'ix_contacts_erpnext_id'),
        ('ix_unified_contacts_zoho_id', 'ix_contacts_zoho_id'),
        ('ix_unified_contacts_legacy_customer_id', 'ix_contacts_legacy_customer_id'),
        ('ix_unified_contacts_legacy_lead_id', 'ix_contacts_legacy_lead_id'),
        ('ix_unified_contacts_legacy_contact_id', 'ix_contacts_legacy_contact_id'),
        ('ix_unified_contacts_account_number', 'ix_contacts_account_number'),
        ('ix_unified_contacts_owner_id', 'ix_contacts_owner_id'),
        ('ix_unified_contacts_territory', 'ix_contacts_territory'),
        ('ix_unified_contacts_source', 'ix_contacts_source'),
        ('ix_unified_contacts_last_contact_date', 'ix_contacts_last_contact_date'),
        ('ix_unified_contacts_created_at', 'ix_contacts_created_at'),
        ('ix_unified_contacts_type_status', 'ix_contacts_type_status'),
        ('ix_unified_contacts_email_type', 'ix_contacts_email_type'),
        ('ix_unified_contacts_phone_type', 'ix_contacts_phone_type'),
        ('ix_unified_contacts_owner_type', 'ix_contacts_owner_type'),
        ('ix_unified_contacts_search_vector', 'ix_contacts_search_vector'),
    ]

    for old_name, new_name in index_renames:
        op.execute(f"ALTER INDEX IF EXISTS {old_name} RENAME TO {new_name};")

    # =========================================================================
    # STEP 6: Rename self-referential FK constraint
    # =========================================================================
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'unified_contacts_parent_id_fkey'
            ) THEN
                ALTER TABLE contacts
                DROP CONSTRAINT unified_contacts_parent_id_fkey,
                ADD CONSTRAINT contacts_parent_id_fkey
                    FOREIGN KEY (parent_id) REFERENCES contacts(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)

    # Rename owner_id FK constraint
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'unified_contacts_owner_id_fkey'
            ) THEN
                ALTER TABLE contacts
                DROP CONSTRAINT unified_contacts_owner_id_fkey,
                ADD CONSTRAINT contacts_owner_id_fkey
                    FOREIGN KEY (owner_id) REFERENCES employees(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)

    # Rename check constraint
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'ck_person_has_parent'
            ) THEN
                ALTER TABLE contacts DROP CONSTRAINT ck_person_has_parent;
                ALTER TABLE contacts ADD CONSTRAINT ck_contacts_person_has_parent
                    CHECK ((contact_type != 'person') OR (parent_id IS NOT NULL));
            END IF;
        END $$;
    """)

    # =========================================================================
    # STEP 7: Recreate search vector trigger with new name
    # =========================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION contacts_search_vector_update()
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

    op.execute("""
        CREATE TRIGGER contacts_search_vector_trigger
        BEFORE INSERT OR UPDATE ON contacts
        FOR EACH ROW
        EXECUTE FUNCTION contacts_search_vector_update();
    """)

    # =========================================================================
    # STEP 8: Add contact_id FK to invoices table
    # =========================================================================
    op.add_column('invoices', sa.Column('contact_id', sa.Integer(), nullable=True))
    op.create_index('ix_invoices_contact_id', 'invoices', ['contact_id'])
    op.create_foreign_key(
        'fk_invoices_contact_id',
        'invoices', 'contacts',
        ['contact_id'], ['id'],
        ondelete='SET NULL'
    )

    # =========================================================================
    # STEP 9: Add contact_id FK to payments table
    # =========================================================================
    op.add_column('payments', sa.Column('contact_id', sa.Integer(), nullable=True))
    op.create_index('ix_payments_contact_id', 'payments', ['contact_id'])
    op.create_foreign_key(
        'fk_payments_contact_id',
        'payments', 'contacts',
        ['contact_id'], ['id'],
        ondelete='SET NULL'
    )

    # =========================================================================
    # STEP 10: Add contact_id FK to credit_notes table
    # =========================================================================
    op.add_column('credit_notes', sa.Column('contact_id', sa.Integer(), nullable=True))
    op.create_index('ix_credit_notes_contact_id', 'credit_notes', ['contact_id'])
    op.create_foreign_key(
        'fk_credit_notes_contact_id',
        'credit_notes', 'contacts',
        ['contact_id'], ['id'],
        ondelete='SET NULL'
    )

    # =========================================================================
    # STEP 11: Drop splynx sync columns from Contact
    # =========================================================================
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS splynx_sync_hash;")
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS last_synced_to_splynx;")


def downgrade() -> None:
    # =========================================================================
    # Remove contact_id from AR tables
    # =========================================================================
    op.drop_constraint('fk_credit_notes_contact_id', 'credit_notes', type_='foreignkey')
    op.drop_index('ix_credit_notes_contact_id', table_name='credit_notes')
    op.drop_column('credit_notes', 'contact_id')

    op.drop_constraint('fk_payments_contact_id', 'payments', type_='foreignkey')
    op.drop_index('ix_payments_contact_id', table_name='payments')
    op.drop_column('payments', 'contact_id')

    op.drop_constraint('fk_invoices_contact_id', 'invoices', type_='foreignkey')
    op.drop_index('ix_invoices_contact_id', table_name='invoices')
    op.drop_column('invoices', 'contact_id')

    # =========================================================================
    # Drop new trigger and function
    # =========================================================================
    op.execute("DROP TRIGGER IF EXISTS contacts_search_vector_trigger ON contacts;")
    op.execute("DROP FUNCTION IF EXISTS contacts_search_vector_update();")

    # =========================================================================
    # Rename table back
    # =========================================================================
    op.rename_table('contacts', 'unified_contacts')

    # =========================================================================
    # Rename indexes back
    # =========================================================================
    index_renames = [
        ('ix_contacts_id', 'ix_unified_contacts_id'),
        ('ix_contacts_contact_type', 'ix_unified_contacts_contact_type'),
        ('ix_contacts_status', 'ix_unified_contacts_status'),
        ('ix_contacts_parent_id', 'ix_unified_contacts_parent_id'),
        ('ix_contacts_is_organization', 'ix_unified_contacts_is_organization'),
        ('ix_contacts_name', 'ix_unified_contacts_name'),
        ('ix_contacts_company_name', 'ix_unified_contacts_company_name'),
        ('ix_contacts_email', 'ix_unified_contacts_email'),
        ('ix_contacts_phone', 'ix_unified_contacts_phone'),
        ('ix_contacts_city', 'ix_unified_contacts_city'),
        ('ix_contacts_state', 'ix_unified_contacts_state'),
        ('ix_contacts_latitude', 'ix_unified_contacts_latitude'),
        ('ix_contacts_longitude', 'ix_unified_contacts_longitude'),
        ('ix_contacts_erpnext_id', 'ix_unified_contacts_erpnext_id'),
        ('ix_contacts_zoho_id', 'ix_unified_contacts_zoho_id'),
        ('ix_contacts_legacy_customer_id', 'ix_unified_contacts_legacy_customer_id'),
        ('ix_contacts_legacy_lead_id', 'ix_unified_contacts_legacy_lead_id'),
        ('ix_contacts_legacy_contact_id', 'ix_unified_contacts_legacy_contact_id'),
        ('ix_contacts_account_number', 'ix_unified_contacts_account_number'),
        ('ix_contacts_owner_id', 'ix_unified_contacts_owner_id'),
        ('ix_contacts_territory', 'ix_unified_contacts_territory'),
        ('ix_contacts_source', 'ix_unified_contacts_source'),
        ('ix_contacts_last_contact_date', 'ix_unified_contacts_last_contact_date'),
        ('ix_contacts_created_at', 'ix_unified_contacts_created_at'),
        ('ix_contacts_type_status', 'ix_unified_contacts_type_status'),
        ('ix_contacts_email_type', 'ix_unified_contacts_email_type'),
        ('ix_contacts_phone_type', 'ix_unified_contacts_phone_type'),
        ('ix_contacts_owner_type', 'ix_unified_contacts_owner_type'),
        ('ix_contacts_search_vector', 'ix_unified_contacts_search_vector'),
    ]

    for old_name, new_name in index_renames:
        op.execute(f"ALTER INDEX IF EXISTS {old_name} RENAME TO {new_name};")

    # =========================================================================
    # Restore ISP-specific columns
    # =========================================================================
    op.add_column('unified_contacts', sa.Column('splynx_id', sa.Integer(), nullable=True))
    op.add_column('unified_contacts', sa.Column('chatwoot_contact_id', sa.Integer(), nullable=True))
    op.add_column('unified_contacts', sa.Column('pop_id', sa.Integer(), nullable=True))
    op.add_column('unified_contacts', sa.Column('base_station', sa.String(255), nullable=True))
    op.add_column('unified_contacts', sa.Column('blocking_date', sa.DateTime(), nullable=True))
    op.add_column('unified_contacts', sa.Column('days_until_blocking', sa.Integer(), nullable=True))
    op.add_column('unified_contacts', sa.Column('legacy_inbox_contact_id', sa.Integer(), nullable=True))
    op.add_column('unified_contacts', sa.Column('splynx_sync_hash', sa.String(64), nullable=True))
    op.add_column('unified_contacts', sa.Column('last_synced_to_splynx', sa.DateTime(), nullable=True))

    # Restore indexes
    op.create_index('ix_unified_contacts_splynx_id', 'unified_contacts', ['splynx_id'], unique=True)
    op.create_index('ix_unified_contacts_chatwoot_contact_id', 'unified_contacts', ['chatwoot_contact_id'])
    op.create_index('ix_unified_contacts_base_station', 'unified_contacts', ['base_station'])

    # Restore FK constraints with old names
    op.execute("""
        ALTER TABLE unified_contacts
        DROP CONSTRAINT IF EXISTS contacts_parent_id_fkey,
        ADD CONSTRAINT unified_contacts_parent_id_fkey
            FOREIGN KEY (parent_id) REFERENCES unified_contacts(id) ON DELETE SET NULL;
    """)

    op.execute("""
        ALTER TABLE unified_contacts
        DROP CONSTRAINT IF EXISTS contacts_owner_id_fkey,
        ADD CONSTRAINT unified_contacts_owner_id_fkey
            FOREIGN KEY (owner_id) REFERENCES employees(id) ON DELETE SET NULL;
    """)

    # Restore check constraint
    op.execute("""
        ALTER TABLE unified_contacts DROP CONSTRAINT IF EXISTS ck_contacts_person_has_parent;
        ALTER TABLE unified_contacts ADD CONSTRAINT ck_person_has_parent
            CHECK ((contact_type != 'person') OR (parent_id IS NOT NULL));
    """)

    # Restore original trigger
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

    op.execute("""
        CREATE TRIGGER unified_contacts_search_vector_trigger
        BEFORE INSERT OR UPDATE ON unified_contacts
        FOR EACH ROW
        EXECUTE FUNCTION unified_contacts_search_vector_update();
    """)
