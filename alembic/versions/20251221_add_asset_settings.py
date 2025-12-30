"""Add asset_settings table

Revision ID: 20251221_add_asset_settings
Revises: fa02400b5de5
Create Date: 2025-12-21

Adds asset_settings table for configuring:
- Default depreciation method and finance book
- Depreciation posting date and auto-posting
- CWIP accounting defaults
- Alert thresholds for maintenance, warranty, and insurance
"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251221_add_asset_settings"
down_revision: Union[str, None] = "fa02400b5de5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Skip if already applied
    if bind and not context.is_offline_mode():
        inspector = sa.inspect(bind)
        if inspector.has_table("asset_settings"):
            return

    op.create_table(
        "asset_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=True, unique=True, index=True),

        # Depreciation defaults
        sa.Column("default_depreciation_method", sa.String(50), nullable=False, server_default="straight_line"),
        sa.Column("default_finance_book", sa.String(255), nullable=True),
        sa.Column("depreciation_posting_date", sa.String(50), nullable=False, server_default="last_day"),
        sa.Column("auto_post_depreciation", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),

        # CWIP (Capital Work in Progress)
        sa.Column("enable_cwip_by_default", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),

        # Alert thresholds (days before event)
        sa.Column("maintenance_alert_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("warranty_alert_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("insurance_alert_days", sa.Integer(), nullable=False, server_default="30"),

        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("asset_settings")
