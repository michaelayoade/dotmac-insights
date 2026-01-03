"""Finalize party migration - make party_id NOT NULL and drop customer_id

IMPORTANT: Only run this AFTER data migration is complete!
Ensure all subscriptions and payment_subscriptions have party_id populated.

Revision ID: party_integration_002
Revises: party_integration_001
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'party_integration_002'
down_revision: Union[str, None] = 'party_integration_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 2: Make party_id NOT NULL and drop customer_id

    # Seed parties and customer_accounts from legacy customers (idempotent).
    op.execute("""
        WITH email_counts AS (
            SELECT lower(email) AS email, COUNT(*) AS cnt
            FROM customers
            WHERE email IS NOT NULL AND email <> ''
            GROUP BY lower(email)
        ),
        phone_counts AS (
            SELECT phone, COUNT(*) AS cnt
            FROM customers
            WHERE phone IS NOT NULL AND phone <> ''
            GROUP BY phone
        )
        INSERT INTO parties (
            type,
            status,
            name,
            primary_email,
            primary_phone,
            external_ids,
            created_at,
            updated_at
        )
        SELECT
            'person' AS type,
            'active' AS status,
            c.name,
            CASE WHEN ec.cnt = 1 THEN c.email ELSE NULL END AS primary_email,
            CASE WHEN pc.cnt = 1 THEN c.phone ELSE NULL END AS primary_phone,
            jsonb_strip_nulls(
                jsonb_build_object(
                    'customer_id', c.id,
                    'splynx_id', c.splynx_id,
                    'erpnext_id', c.erpnext_id,
                    'account_number', c.account_number
                )
            ) AS external_ids,
            c.created_at,
            c.updated_at
        FROM customers c
        LEFT JOIN email_counts ec ON lower(c.email) = ec.email
        LEFT JOIN phone_counts pc ON c.phone = pc.phone
        WHERE NOT EXISTS (
            SELECT 1 FROM parties p
            WHERE p.external_ids->>'customer_id' = c.id::text
        );
    """)

    op.execute("""
        INSERT INTO party_external_ids (
            party_id, system, external_id, external_key_type, is_primary
        )
        SELECT p.id, 'legacy', c.id::text, 'customer_id', true
        FROM customers c
        JOIN parties p ON p.external_ids->>'customer_id' = c.id::text
        WHERE NOT EXISTS (
            SELECT 1 FROM party_external_ids pe
            WHERE pe.system = 'legacy' AND pe.external_id = c.id::text
        );
    """)

    op.execute("""
        INSERT INTO party_external_ids (
            party_id, system, external_id, external_key_type, is_primary
        )
        SELECT p.id, 'splynx', c.splynx_id::text, 'customer_id', false
        FROM customers c
        JOIN parties p ON p.external_ids->>'customer_id' = c.id::text
        WHERE c.splynx_id IS NOT NULL
        ON CONFLICT (system, external_id) DO NOTHING;
    """)

    op.execute("""
        INSERT INTO party_external_ids (
            party_id, system, external_id, external_key_type, is_primary
        )
        SELECT p.id, 'erpnext', c.erpnext_id, 'customer_id', false
        FROM customers c
        JOIN parties p ON p.external_ids->>'customer_id' = c.id::text
        WHERE c.erpnext_id IS NOT NULL
        ON CONFLICT (system, external_id) DO NOTHING;
    """)

    op.execute("""
        WITH account_counts AS (
            SELECT account_number, COUNT(*) AS cnt
            FROM customers
            WHERE account_number IS NOT NULL AND account_number <> ''
            GROUP BY account_number
        )
        INSERT INTO customer_accounts (
            party_id,
            account_number,
            status,
            external_ids,
            created_at,
            activated_at
        )
        SELECT
            p.id,
            CASE
                WHEN ac.cnt = 1 AND c.account_number IS NOT NULL AND c.account_number <> '' THEN c.account_number
                WHEN c.splynx_id IS NOT NULL THEN 'splynx-' || c.splynx_id::text
                WHEN c.erpnext_id IS NOT NULL THEN 'erpnext-' || c.erpnext_id
                ELSE 'legacy-' || c.id::text
            END AS account_number,
            CASE
                WHEN c.status::text = 'ACTIVE' THEN 'active'
                WHEN c.status::text = 'SUSPENDED' THEN 'suspended'
                WHEN c.status::text = 'PROSPECT' THEN 'pending'
                WHEN c.status::text = 'INACTIVE' THEN 'suspended'
                ELSE 'active'
            END AS status,
            jsonb_strip_nulls(
                jsonb_build_object(
                    'customer_id', c.id,
                    'splynx_id', c.splynx_id,
                    'erpnext_id', c.erpnext_id,
                    'account_number', c.account_number
                )
            ) AS external_ids,
            c.created_at,
            c.activation_date
        FROM customers c
        JOIN parties p ON p.external_ids->>'customer_id' = c.id::text
        LEFT JOIN account_counts ac ON c.account_number = ac.account_number
        WHERE NOT EXISTS (
            SELECT 1 FROM customer_accounts ca WHERE ca.party_id = p.id
        );
    """)

    op.execute("""
        UPDATE subscriptions s
        SET party_id = p.id
        FROM parties p
        WHERE p.external_ids->>'customer_id' = s.customer_id::text
          AND s.party_id IS NULL
    """)

    op.execute("""
        UPDATE payment_subscriptions ps
        SET party_id = p.id
        FROM parties p
        WHERE p.external_ids->>'customer_id' = ps.customer_id::text
          AND ps.party_id IS NULL
    """)

    # Backfill party_id from legacy customers via external ID mappings.
    op.execute("""
        UPDATE subscriptions s
        SET party_id = pe.party_id
        FROM customers c
        JOIN party_external_ids pe
          ON pe.system = 'erpnext'
         AND pe.external_id = c.erpnext_id
        WHERE s.customer_id = c.id
          AND s.party_id IS NULL
          AND c.erpnext_id IS NOT NULL
    """)

    op.execute("""
        UPDATE subscriptions s
        SET party_id = pe.party_id
        FROM customers c
        JOIN party_external_ids pe
          ON pe.system = 'splynx'
         AND pe.external_id = c.splynx_id::text
        WHERE s.customer_id = c.id
          AND s.party_id IS NULL
          AND c.splynx_id IS NOT NULL
    """)

    op.execute("""
        UPDATE payment_subscriptions ps
        SET party_id = pe.party_id
        FROM customers c
        JOIN party_external_ids pe
          ON pe.system = 'erpnext'
         AND pe.external_id = c.erpnext_id
        WHERE ps.customer_id = c.id
          AND ps.party_id IS NULL
          AND c.erpnext_id IS NOT NULL
    """)

    op.execute("""
        UPDATE payment_subscriptions ps
        SET party_id = pe.party_id
        FROM customers c
        JOIN party_external_ids pe
          ON pe.system = 'splynx'
         AND pe.external_id = c.splynx_id::text
        WHERE ps.customer_id = c.id
          AND ps.party_id IS NULL
          AND c.splynx_id IS NOT NULL
    """)

    # Fallback: map via customer_accounts when external IDs are missing.
    op.execute("""
        UPDATE subscriptions s
        SET party_id = ca.party_id
        FROM customers c
        JOIN customer_accounts ca
          ON ca.external_ids->>'erpnext_id' = c.erpnext_id
        WHERE s.customer_id = c.id
          AND s.party_id IS NULL
          AND c.erpnext_id IS NOT NULL
    """)

    op.execute("""
        UPDATE subscriptions s
        SET party_id = ca.party_id
        FROM customers c
        JOIN customer_accounts ca
          ON ca.external_ids->>'splynx_id' = c.splynx_id::text
        WHERE s.customer_id = c.id
          AND s.party_id IS NULL
          AND c.splynx_id IS NOT NULL
    """)

    op.execute("""
        UPDATE subscriptions s
        SET party_id = ca.party_id
        FROM customers c
        JOIN customer_accounts ca
          ON ca.account_number = c.account_number
        WHERE s.customer_id = c.id
          AND s.party_id IS NULL
          AND c.account_number IS NOT NULL
    """)

    op.execute("""
        UPDATE payment_subscriptions ps
        SET party_id = ca.party_id
        FROM customers c
        JOIN customer_accounts ca
          ON ca.external_ids->>'erpnext_id' = c.erpnext_id
        WHERE ps.customer_id = c.id
          AND ps.party_id IS NULL
          AND c.erpnext_id IS NOT NULL
    """)

    op.execute("""
        UPDATE payment_subscriptions ps
        SET party_id = ca.party_id
        FROM customers c
        JOIN customer_accounts ca
          ON ca.external_ids->>'splynx_id' = c.splynx_id::text
        WHERE ps.customer_id = c.id
          AND ps.party_id IS NULL
          AND c.splynx_id IS NOT NULL
    """)

    op.execute("""
        UPDATE payment_subscriptions ps
        SET party_id = ca.party_id
        FROM customers c
        JOIN customer_accounts ca
          ON ca.account_number = c.account_number
        WHERE ps.customer_id = c.id
          AND ps.party_id IS NULL
          AND c.account_number IS NOT NULL
    """)

    # Guard before enforcing NOT NULL.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM subscriptions WHERE party_id IS NULL) THEN
                RAISE EXCEPTION 'subscriptions.party_id still NULL after backfill';
            END IF;
            IF EXISTS (SELECT 1 FROM payment_subscriptions WHERE party_id IS NULL) THEN
                RAISE EXCEPTION 'payment_subscriptions.party_id still NULL after backfill';
            END IF;
        END $$;
    """)

    # Subscriptions: make party_id NOT NULL
    op.alter_column('subscriptions', 'party_id',
        existing_type=sa.BigInteger(),
        nullable=False
    )

    # Subscriptions: drop customer_id
    op.drop_constraint('subscriptions_customer_id_fkey', 'subscriptions', type_='foreignkey')
    op.drop_index('ix_subscriptions_customer_id', table_name='subscriptions')
    op.drop_column('subscriptions', 'customer_id')

    # Payment subscriptions: make party_id NOT NULL
    op.alter_column('payment_subscriptions', 'party_id',
        existing_type=sa.BigInteger(),
        nullable=False
    )

    # Payment subscriptions: drop customer_id and update index
    op.drop_constraint('payment_subscriptions_customer_id_fkey', 'payment_subscriptions', type_='foreignkey')
    op.drop_index('ix_payment_sub_customer_status', table_name='payment_subscriptions')
    op.drop_column('payment_subscriptions', 'customer_id')

    # Create new party_status index for payment_subscriptions
    op.create_index(
        'ix_payment_sub_party_status',
        'payment_subscriptions',
        ['party_id', 'status']
    )


def downgrade() -> None:
    # This is a destructive migration - downgrade requires data restoration
    # Re-add customer_id columns

    # Payment subscriptions: drop new index
    op.drop_index('ix_payment_sub_party_status', table_name='payment_subscriptions')

    # Payment subscriptions: add back customer_id
    op.add_column('payment_subscriptions',
        sa.Column('customer_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'payment_subscriptions_customer_id_fkey',
        'payment_subscriptions', 'customers',
        ['customer_id'], ['id']
    )
    op.create_index(
        'ix_payment_sub_customer_status',
        'payment_subscriptions',
        ['customer_id', 'status']
    )

    # Payment subscriptions: make party_id nullable again
    op.alter_column('payment_subscriptions', 'party_id',
        existing_type=sa.BigInteger(),
        nullable=True
    )

    # Subscriptions: add back customer_id
    op.add_column('subscriptions',
        sa.Column('customer_id', sa.Integer(), nullable=True)
    )
    op.create_index('ix_subscriptions_customer_id', 'subscriptions', ['customer_id'])
    op.create_foreign_key(
        'subscriptions_customer_id_fkey',
        'subscriptions', 'customers',
        ['customer_id'], ['id']
    )

    # Subscriptions: make party_id nullable again
    op.alter_column('subscriptions', 'party_id',
        existing_type=sa.BigInteger(),
        nullable=True
    )
