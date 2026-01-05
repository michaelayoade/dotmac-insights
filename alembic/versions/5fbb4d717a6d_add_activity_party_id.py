"""add activity party id

Revision ID: 5fbb4d717a6d
Revises: 99b8a398e3dd
Create Date: 2026-01-02 16:44:42.982044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5fbb4d717a6d'
down_revision: Union[str, None] = '99b8a398e3dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("party_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_activities_party_id", "activities", ["party_id"], unique=False)
    op.create_foreign_key(
        "fk_activities_party_id_parties",
        "activities",
        "parties",
        ["party_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_activities_party_id_parties", "activities", type_="foreignkey")
    op.drop_index("ix_activities_party_id", table_name="activities")
    op.drop_column("activities", "party_id")
