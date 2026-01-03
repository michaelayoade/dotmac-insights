"""add omni webhook retry fields

Revision ID: b3c9e1a7f4b2
Revises: d1b9312c04ad
Create Date: 2026-01-02 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3c9e1a7f4b2"
down_revision: Union[str, None] = "d1b9312c04ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "omni_webhook_events",
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "omni_webhook_events",
        sa.Column("last_retry_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("omni_webhook_events", "last_retry_at")
    op.drop_column("omni_webhook_events", "retry_count")
