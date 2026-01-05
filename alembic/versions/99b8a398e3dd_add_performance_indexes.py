"""add performance indexes

Revision ID: 99b8a398e3dd
Revises: 20178a73eace
Create Date: 2026-01-02 15:37:42.753645

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99b8a398e3dd'
down_revision: Union[str, None] = '20178a73eace'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bank_transactions_transaction_id "
        "ON bank_transactions (transaction_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_sender_id "
        "ON messages (sender_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversations_assigned_agent_id "
        "ON conversations (assigned_agent_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversations_assigned_team_id "
        "ON conversations (assigned_team_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_credit_notes_posting_date "
        "ON credit_notes (posting_date);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_credit_notes_fiscal_period_id "
        "ON credit_notes (fiscal_period_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tickets_merged_into_id "
        "ON tickets (merged_into_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tickets_parent_ticket_id "
        "ON tickets (parent_ticket_id);"
    )


def downgrade() -> None:
    op.drop_index("ix_tickets_parent_ticket_id", table_name="tickets")
    op.drop_index("ix_tickets_merged_into_id", table_name="tickets")
    op.drop_index("ix_credit_notes_fiscal_period_id", table_name="credit_notes")
    op.drop_index("ix_credit_notes_posting_date", table_name="credit_notes")
    op.drop_index("ix_conversations_assigned_team_id", table_name="conversations")
    op.drop_index("ix_conversations_assigned_agent_id", table_name="conversations")
    op.drop_index("ix_messages_sender_id", table_name="messages")
    op.drop_index("ix_bank_transactions_transaction_id", table_name="bank_transactions")
