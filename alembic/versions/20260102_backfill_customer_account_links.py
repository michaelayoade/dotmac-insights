"""Backfill customer_account_id on invoices and payments.

Revision ID: 20260102_backfill_customer_account_links
Revises: 20260102_add_customer_account_links
Create Date: 2026-01-02
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260102_backfill_customer_account_links"
down_revision = "20260102_add_customer_account_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill from legacy customers via ERPNext IDs
    op.execute(
        """
        UPDATE invoices i
        SET customer_account_id = ca.id
        FROM customers c
        JOIN party_external_ids pe
          ON pe.system = 'erpnext'
         AND pe.external_id = c.erpnext_id
        JOIN customer_accounts ca
          ON ca.party_id = pe.party_id
        WHERE i.customer_account_id IS NULL
          AND i.customer_id = c.id
          AND c.erpnext_id IS NOT NULL;
        """
    )

    op.execute(
        """
        UPDATE payments p
        SET customer_account_id = ca.id
        FROM customers c
        JOIN party_external_ids pe
          ON pe.system = 'erpnext'
         AND pe.external_id = c.erpnext_id
        JOIN customer_accounts ca
          ON ca.party_id = pe.party_id
        WHERE p.customer_account_id IS NULL
          AND p.customer_id = c.id
          AND c.erpnext_id IS NOT NULL;
        """
    )

    # Backfill from legacy customers via Splynx IDs
    op.execute(
        """
        UPDATE invoices i
        SET customer_account_id = ca.id
        FROM customers c
        JOIN party_external_ids pe
          ON pe.system = 'splynx'
         AND pe.external_id = c.splynx_id::text
        JOIN customer_accounts ca
          ON ca.party_id = pe.party_id
        WHERE i.customer_account_id IS NULL
          AND i.customer_id = c.id
          AND c.splynx_id IS NOT NULL;
        """
    )

    op.execute(
        """
        UPDATE payments p
        SET customer_account_id = ca.id
        FROM customers c
        JOIN party_external_ids pe
          ON pe.system = 'splynx'
         AND pe.external_id = c.splynx_id::text
        JOIN customer_accounts ca
          ON ca.party_id = pe.party_id
        WHERE p.customer_account_id IS NULL
          AND p.customer_id = c.id
          AND c.splynx_id IS NOT NULL;
        """
    )

    # Fallback: link via contacts (ERPNext ID)
    op.execute(
        """
        UPDATE invoices i
        SET customer_account_id = ca.id
        FROM contacts ct
        JOIN party_external_ids pe
          ON pe.system = 'erpnext'
         AND pe.external_id = ct.erpnext_id
        JOIN customer_accounts ca
          ON ca.party_id = pe.party_id
        WHERE i.customer_account_id IS NULL
          AND i.contact_id = ct.id
          AND ct.erpnext_id IS NOT NULL;
        """
    )

    op.execute(
        """
        UPDATE payments p
        SET customer_account_id = ca.id
        FROM contacts ct
        JOIN party_external_ids pe
          ON pe.system = 'erpnext'
         AND pe.external_id = ct.erpnext_id
        JOIN customer_accounts ca
          ON ca.party_id = pe.party_id
        WHERE p.customer_account_id IS NULL
          AND p.contact_id = ct.id
          AND ct.erpnext_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    # Data backfill is not reversed.
    pass
