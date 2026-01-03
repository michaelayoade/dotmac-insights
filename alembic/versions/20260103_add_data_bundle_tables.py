"""add_data_bundle_tables

Revision ID: a1b2c3d4e5f6
Revises: b284a20bc2a9
Create Date: 2026-01-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'b284a20bc2a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============= DATA BUNDLE PRODUCTS =============
    op.create_table(
        'data_bundle_products',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('bundle_type', sa.String(20), nullable=False, default='prepaid'),

        # Data allocation
        sa.Column('data_amount_mb', sa.Integer(), nullable=True),
        sa.Column('data_cap_mb', sa.Integer(), nullable=True),

        # Pricing
        sa.Column('price', sa.Numeric(precision=18, scale=4), nullable=False, default=0),
        sa.Column('currency', sa.String(3), nullable=False, default='NGN'),

        # Usage-based pricing tiers (JSON)
        sa.Column('usage_tiers', postgresql.JSONB(), nullable=True),

        # Overage pricing for hybrid bundles
        sa.Column('overage_price_per_mb', sa.Numeric(precision=18, scale=6), nullable=True),

        # Expiry configuration
        sa.Column('expiry_type', sa.String(20), nullable=False, default='strict'),
        sa.Column('validity_days', sa.Integer(), nullable=True, default=30),
        sa.Column('rollover_percent', sa.Integer(), nullable=True, default=0),

        # Exhaustion behavior
        sa.Column('exhaustion_action', sa.String(20), nullable=False, default='throttle'),
        sa.Column('throttle_speed_kbps', sa.Integer(), nullable=True, default=128),
        sa.Column('auto_renew_product_id', sa.Integer(), sa.ForeignKey('data_bundle_products.id', ondelete='SET NULL'), nullable=True),

        # Speed limits
        sa.Column('download_speed_kbps', sa.Integer(), nullable=True),
        sa.Column('upload_speed_kbps', sa.Integer(), nullable=True),

        # Alert thresholds
        sa.Column('alert_threshold_1', sa.Integer(), nullable=False, default=50),
        sa.Column('alert_threshold_2', sa.Integer(), nullable=False, default=80),
        sa.Column('alert_threshold_3', sa.Integer(), nullable=False, default=95),

        # Availability
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        sa.Column('customer_portal_visible', sa.Boolean(), nullable=False, default=True),

        # Categorization
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('tags', postgresql.JSONB(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ============= CUSTOMER BUNDLES =============
    op.create_table(
        'customer_bundles',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),

        # Links
        sa.Column('subscription_id', sa.Integer(), sa.ForeignKey('subscriptions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('data_bundle_products.id', ondelete='RESTRICT'), nullable=False, index=True),

        # Data allocation
        sa.Column('data_allocated_mb', sa.Integer(), nullable=False, default=0),
        sa.Column('data_used_mb', sa.Integer(), nullable=False, default=0),
        sa.Column('rollover_mb', sa.Integer(), nullable=False, default=0),

        # Status
        sa.Column('status', sa.String(20), nullable=False, default='pending', index=True),

        # Dates
        sa.Column('purchased_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('exhausted_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),

        # Billing
        sa.Column('amount_charged', sa.Numeric(precision=18, scale=4), nullable=False, default=0),
        sa.Column('currency', sa.String(3), nullable=False, default='NGN'),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('invoices.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('payment_reference', sa.String(100), nullable=True),

        # Alert tracking
        sa.Column('alert_50_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('alert_80_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('alert_95_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('exhaustion_alert_sent', sa.Boolean(), nullable=False, default=False),

        # Renewal tracking
        sa.Column('renewed_from_bundle_id', sa.Integer(), sa.ForeignKey('customer_bundles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('auto_renewed', sa.Boolean(), nullable=False, default=False),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create composite indexes
    op.create_index('ix_customer_bundles_active', 'customer_bundles', ['subscription_id', 'status'])
    op.create_index('ix_customer_bundles_expiry', 'customer_bundles', ['expires_at', 'status'])

    # ============= BUNDLE USAGE LOGS =============
    op.create_table(
        'bundle_usage_logs',
        sa.Column('id', sa.BigInteger(), primary_key=True, index=True),
        sa.Column('customer_bundle_id', sa.Integer(), sa.ForeignKey('customer_bundles.id', ondelete='CASCADE'), nullable=False, index=True),

        # Usage data
        sa.Column('recorded_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('upload_bytes', sa.BigInteger(), nullable=False, default=0),
        sa.Column('download_bytes', sa.BigInteger(), nullable=False, default=0),

        # Source tracking
        sa.Column('source', sa.String(20), nullable=False, default='RADIUS'),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('nas_ip', sa.String(45), nullable=True),
    )

    # Create composite index for time-based queries
    op.create_index('ix_bundle_usage_logs_bundle_time', 'bundle_usage_logs', ['customer_bundle_id', 'recorded_at'])

    # ============= BUNDLE TRANSACTIONS =============
    op.create_table(
        'bundle_transactions',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('customer_bundle_id', sa.Integer(), sa.ForeignKey('customer_bundles.id', ondelete='CASCADE'), nullable=False, index=True),

        # Transaction details
        sa.Column('transaction_type', sa.String(20), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='NGN'),

        # Usage context
        sa.Column('data_mb', sa.Integer(), nullable=True),
        sa.Column('tier_applied', sa.String(50), nullable=True),
        sa.Column('rate_per_mb', sa.Numeric(precision=18, scale=6), nullable=True),

        # Reference
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('invoices.id', ondelete='SET NULL'), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table('bundle_transactions')
    op.drop_index('ix_bundle_usage_logs_bundle_time')
    op.drop_table('bundle_usage_logs')
    op.drop_index('ix_customer_bundles_expiry')
    op.drop_index('ix_customer_bundles_active')
    op.drop_table('customer_bundles')
    op.drop_table('data_bundle_products')
