"""Backfill customer_account_id for conversations from Chatwoot mappings.

Revision ID: 20260102_backfill_conversation_customer_account
Revises: 20260102_add_conversation_customer_account
Create Date: 2026-01-02
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260102_backfill_conversation_customer_account"
down_revision = "20260102_add_conversation_customer_account"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE conversations c
        SET customer_account_id = ca.id
        FROM party_external_ids pe
        JOIN customer_accounts ca
          ON ca.party_id = pe.party_id
        WHERE c.customer_account_id IS NULL
          AND c.chatwoot_contact_id IS NOT NULL
          AND pe.system = 'chatwoot'
          AND pe.external_key_type = 'contact_id'
          AND pe.external_id = c.chatwoot_contact_id::text;
        """
    )


def downgrade() -> None:
    # Data backfill is not reversed.
    pass
