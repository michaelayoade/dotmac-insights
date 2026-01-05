"""add_party_profile_fields

Revision ID: c32bdad740a3
Revises: 7c9d1e2f3a4b
Create Date: 2026-01-04 19:16:07.709219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c32bdad740a3'
down_revision: Union[str, None] = '7c9d1e2f3a4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("parties", sa.Column("linkedin_url", sa.Text(), nullable=True))
    op.add_column("parties", sa.Column("twitter_handle", sa.Text(), nullable=True))
    op.add_column("parties", sa.Column("facebook_url", sa.Text(), nullable=True))
    op.add_column("parties", sa.Column("instagram_handle", sa.Text(), nullable=True))
    op.add_column("parties", sa.Column("website_url", sa.Text(), nullable=True))
    op.add_column("parties", sa.Column("preferred_channel", sa.Text(), nullable=True))
    op.add_column(
        "parties",
        sa.Column("do_not_contact", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("parties", sa.Column("contact_frequency_limit", sa.Integer(), nullable=True))
    op.add_column("parties", sa.Column("engagement_score", sa.Integer(), nullable=True))
    op.add_column("parties", sa.Column("last_engagement_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("parties", sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("parties", "last_contacted_at")
    op.drop_column("parties", "last_engagement_at")
    op.drop_column("parties", "engagement_score")
    op.drop_column("parties", "contact_frequency_limit")
    op.drop_column("parties", "do_not_contact")
    op.drop_column("parties", "preferred_channel")
    op.drop_column("parties", "website_url")
    op.drop_column("parties", "instagram_handle")
    op.drop_column("parties", "facebook_url")
    op.drop_column("parties", "twitter_handle")
    op.drop_column("parties", "linkedin_url")
