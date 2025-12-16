"""Enforce unified_contact_id NOT NULL after cutover verification

This migration:
1. Verifies all existing records have unified_contact_id populated
2. Makes unified_contact_id columns NOT NULL
3. Should be run ONLY after dual-write period is complete and verified

IMPORTANT: Do NOT run this migration until you have verified:
- All existing records have unified_contact_id populated
- Application code creates UnifiedContact records for all new contacts
- Legacy direct-insert code paths have been updated

Run this query to check readiness:
    SELECT
        'customers' as tbl, COUNT(*) as orphaned FROM customers WHERE unified_contact_id IS NULL
        UNION ALL
        SELECT 'opportunities', COUNT(*) FROM opportunities WHERE unified_contact_id IS NULL AND (customer_id IS NOT NULL OR lead_id IS NOT NULL)
        UNION ALL
        SELECT 'activities', COUNT(*) FROM activities WHERE unified_contact_id IS NULL AND (customer_id IS NOT NULL OR lead_id IS NOT NULL OR contact_id IS NOT NULL)
        UNION ALL
        SELECT 'contacts', COUNT(*) FROM contacts WHERE unified_contact_id IS NULL
        UNION ALL
        SELECT 'omni_conversations', COUNT(*) FROM omni_conversations WHERE unified_contact_id IS NULL AND (customer_id IS NOT NULL OR lead_id IS NOT NULL OR contact_email IS NOT NULL)
        UNION ALL
        SELECT 'omni_participants', COUNT(*) FROM omni_participants WHERE unified_contact_id IS NULL AND customer_id IS NOT NULL
        UNION ALL
        SELECT 'inbox_contacts', COUNT(*) FROM inbox_contacts WHERE unified_contact_id IS NULL;

All counts should be 0 before running this migration.

Revision ID: uc003_enforce_not_null
Revises: uc002_migrate_contacts
Create Date: 2025-12-16
"""
from alembic import op
import sqlalchemy as sa

revision = 'uc003_enforce_not_null'
down_revision = 'uc002_migrate_contacts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # STEP 0: Pre-flight check - abort if orphaned records exist
    # =========================================================================
    conn = op.get_bind()

    # Check for orphaned customers (must all have unified_contact_id)
    orphaned_customers = conn.execute(sa.text(
        "SELECT COUNT(*) FROM customers WHERE unified_contact_id IS NULL"
    )).scalar()
    if orphaned_customers > 0:
        raise RuntimeError(
            f"ABORT: {orphaned_customers} customers lack unified_contact_id. "
            "Run the backfill script before enforcing NOT NULL."
        )

    # Check for orphaned contacts (CRM)
    orphaned_contacts = conn.execute(sa.text(
        "SELECT COUNT(*) FROM contacts WHERE unified_contact_id IS NULL"
    )).scalar()
    if orphaned_contacts > 0:
        raise RuntimeError(
            f"ABORT: {orphaned_contacts} CRM contacts lack unified_contact_id. "
            "Run the backfill script before enforcing NOT NULL."
        )

    # Check for orphaned inbox_contacts
    orphaned_inbox = conn.execute(sa.text(
        "SELECT COUNT(*) FROM inbox_contacts WHERE unified_contact_id IS NULL"
    )).scalar()
    if orphaned_inbox > 0:
        raise RuntimeError(
            f"ABORT: {orphaned_inbox} inbox contacts lack unified_contact_id. "
            "Run the backfill script before enforcing NOT NULL."
        )

    # =========================================================================
    # STEP 1: Log enforcement for audit
    # =========================================================================
    op.execute("""
        INSERT INTO unified_contact_migration_log (source_table, source_id, conflict_type, conflict_value)
        VALUES ('ENFORCEMENT', 0, 'not_null_enforced', NOW()::text)
    """)

    # =========================================================================
    # STEP 2: Make customers.unified_contact_id NOT NULL
    # =========================================================================
    op.alter_column('customers', 'unified_contact_id',
                    existing_type=sa.Integer(),
                    nullable=False)

    # =========================================================================
    # STEP 3: Make contacts.unified_contact_id NOT NULL
    # =========================================================================
    op.alter_column('contacts', 'unified_contact_id',
                    existing_type=sa.Integer(),
                    nullable=False)

    # =========================================================================
    # STEP 4: Make inbox_contacts.unified_contact_id NOT NULL
    # =========================================================================
    op.alter_column('inbox_contacts', 'unified_contact_id',
                    existing_type=sa.Integer(),
                    nullable=False)

    # =========================================================================
    # NOTE: We keep the following columns NULLABLE because these records
    # can legitimately exist without a contact reference:
    # - opportunities.unified_contact_id (some opps may be company-level, not contact-level)
    # - activities.unified_contact_id (some activities may be internal/system)
    # - omni_conversations.unified_contact_id (anonymous/unknown senders)
    # - omni_participants.unified_contact_id (external participants)
    # =========================================================================


def downgrade() -> None:
    # Revert to nullable (for rollback safety)
    op.alter_column('inbox_contacts', 'unified_contact_id',
                    existing_type=sa.Integer(),
                    nullable=True)

    op.alter_column('contacts', 'unified_contact_id',
                    existing_type=sa.Integer(),
                    nullable=True)

    op.alter_column('customers', 'unified_contact_id',
                    existing_type=sa.Integer(),
                    nullable=True)

    op.execute("""
        INSERT INTO unified_contact_migration_log (source_table, source_id, conflict_type, conflict_value)
        VALUES ('ENFORCEMENT', 0, 'not_null_reverted', NOW()::text)
    """)
