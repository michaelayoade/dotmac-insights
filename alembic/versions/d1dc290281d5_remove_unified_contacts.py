"""remove unified contacts

Revision ID: d1dc290281d5
Revises: 3b28128f2004
Create Date: 2026-01-02 14:39:08.918647

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1dc290281d5'
down_revision: Union[str, None] = '3b28128f2004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("party_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_opportunities_party_id", "opportunities", ["party_id"], unique=False)
    op.create_foreign_key(
        "fk_opportunities_party_id",
        "opportunities",
        "parties",
        ["party_id"],
        ["id"],
    )
    op.execute(
        "ALTER TABLE opportunities DROP CONSTRAINT IF EXISTS opportunities_unified_contact_id_fkey"
    )
    op.execute("DROP INDEX IF EXISTS ix_opportunities_unified_contact_id")
    op.execute("ALTER TABLE opportunities DROP COLUMN IF EXISTS unified_contact_id")

    op.add_column("unified_tickets", sa.Column("party_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_unified_tickets_party_id", "unified_tickets", ["party_id"], unique=False)
    op.create_foreign_key(
        "fk_unified_tickets_party_id",
        "unified_tickets",
        "parties",
        ["party_id"],
        ["id"],
    )
    op.execute("DROP INDEX IF EXISTS ix_unified_tickets_contact_status")
    op.create_index(
        "ix_unified_tickets_party_status",
        "unified_tickets",
        ["party_id", "status"],
        unique=False,
    )
    op.execute(
        "ALTER TABLE unified_tickets DROP CONSTRAINT IF EXISTS unified_tickets_unified_contact_id_fkey"
    )
    op.execute("DROP INDEX IF EXISTS ix_unified_tickets_unified_contact_id")
    op.execute("ALTER TABLE unified_tickets DROP COLUMN IF EXISTS unified_contact_id")

    op.add_column("omni_conversations", sa.Column("party_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_omni_conversations_party_id", "omni_conversations", ["party_id"], unique=False)
    op.create_foreign_key(
        "fk_omni_conversations_party_id",
        "omni_conversations",
        "parties",
        ["party_id"],
        ["id"],
    )
    op.execute(
        "ALTER TABLE omni_conversations DROP CONSTRAINT IF EXISTS omni_conversations_unified_contact_id_fkey"
    )
    op.execute("DROP INDEX IF EXISTS ix_omni_conversations_unified_contact_id")
    op.execute("ALTER TABLE omni_conversations DROP COLUMN IF EXISTS unified_contact_id")

    op.add_column("omni_participants", sa.Column("party_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_omni_participants_party_id", "omni_participants", ["party_id"], unique=False)
    op.create_foreign_key(
        "fk_omni_participants_party_id",
        "omni_participants",
        "parties",
        ["party_id"],
        ["id"],
    )
    op.execute(
        "ALTER TABLE omni_participants DROP CONSTRAINT IF EXISTS omni_participants_unified_contact_id_fkey"
    )
    op.execute("DROP INDEX IF EXISTS ix_omni_participants_unified_contact_id")
    op.execute("ALTER TABLE omni_participants DROP COLUMN IF EXISTS unified_contact_id")

    op.add_column("inbox_contacts", sa.Column("party_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_inbox_contacts_party_id", "inbox_contacts", ["party_id"], unique=False)
    op.create_foreign_key(
        "fk_inbox_contacts_party_id",
        "inbox_contacts",
        "parties",
        ["party_id"],
        ["id"],
    )
    op.execute(
        "ALTER TABLE inbox_contacts DROP CONSTRAINT IF EXISTS inbox_contacts_unified_contact_id_fkey"
    )
    op.execute("DROP INDEX IF EXISTS ix_inbox_contacts_unified_contact_id")
    op.execute("ALTER TABLE inbox_contacts DROP COLUMN IF EXISTS unified_contact_id")

    op.execute("ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_unified_contact_id_fkey")
    op.execute("DROP INDEX IF EXISTS ix_customers_unified_contact_id")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS unified_contact_id")

    op.execute("DROP TABLE IF EXISTS unified_contacts CASCADE")


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for UnifiedContact retirement.")
