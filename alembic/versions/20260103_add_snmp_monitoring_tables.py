"""Add SNMP monitoring and metrics tables

Revision ID: snmp001_add_monitoring
Revises: a1b2c3d4e5f6
Create Date: 2026-01-03

Creates tables for NOC monitoring via SNMP:
- snmp_polling_configs: Per-router SNMP configuration
- device_metrics: Device-level metrics (CPU, memory, uptime)
- interface_metrics: Per-interface traffic metrics
- interface_states: Current interface state snapshots
- interface_metric_rollups: Aggregated metrics for historical graphs
- subscription_usage_metrics: Per-subscription daily usage
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime


revision: str = 'snmp001_add_monitoring'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # SNMP POLLING CONFIGS
    # =========================================================================
    op.create_table(
        'snmp_polling_configs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('router_id', sa.Integer(), sa.ForeignKey('routers.id', ondelete='CASCADE'),
                  unique=True, index=True, nullable=False),

        # SNMP Version
        sa.Column('snmp_version', sa.String(10), nullable=False, server_default='2c'),

        # SNMPv2c settings
        sa.Column('community', sa.String(255), nullable=True),  # Encrypted

        # SNMPv3 settings
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('auth_protocol', sa.String(20), nullable=True),  # md5, sha, sha256, etc.
        sa.Column('auth_password', sa.String(255), nullable=True),  # Encrypted
        sa.Column('priv_protocol', sa.String(20), nullable=True),  # des, aes, aes256
        sa.Column('priv_password', sa.String(255), nullable=True),  # Encrypted

        # Polling settings
        sa.Column('polling_interval_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('port', sa.Integer(), nullable=False, server_default='161'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('retries', sa.Integer(), nullable=False, server_default='2'),

        # Status
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true', index=True),
        sa.Column('last_polled_at', sa.DateTime(), nullable=True),
        sa.Column('last_poll_status', sa.String(20), nullable=True),  # success, timeout, auth_error, etc.
        sa.Column('last_poll_error', sa.Text(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(),
                  onupdate=datetime.utcnow),
    )

    # =========================================================================
    # DEVICE METRICS (time-series)
    # =========================================================================
    op.create_table(
        'device_metrics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('router_id', sa.Integer(), sa.ForeignKey('routers.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),

        # System metrics
        sa.Column('uptime_seconds', sa.BigInteger(), nullable=True),
        sa.Column('cpu_percent', sa.Float(), nullable=True),
        sa.Column('memory_percent', sa.Float(), nullable=True),
        sa.Column('memory_used_bytes', sa.BigInteger(), nullable=True),
        sa.Column('memory_total_bytes', sa.BigInteger(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),

        # Aggregated traffic (all interfaces combined)
        sa.Column('total_rx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_tx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_rx_rate_bps', sa.BigInteger(), nullable=True),
        sa.Column('total_tx_rate_bps', sa.BigInteger(), nullable=True),

        # Active sessions (MikroTik-specific)
        sa.Column('active_ppp_sessions', sa.Integer(), nullable=True),
        sa.Column('active_hotspot_sessions', sa.Integer(), nullable=True),
        sa.Column('active_dhcp_leases', sa.Integer(), nullable=True),
    )
    op.create_index('ix_device_metrics_router_timestamp', 'device_metrics',
                    ['router_id', 'timestamp'])

    # =========================================================================
    # INTERFACE METRICS (time-series)
    # =========================================================================
    op.create_table(
        'interface_metrics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('router_id', sa.Integer(), sa.ForeignKey('routers.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('interface_index', sa.Integer(), nullable=False, index=True),
        sa.Column('interface_name', sa.String(100), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),

        # Traffic counters (64-bit from ifHCInOctets/ifHCOutOctets)
        sa.Column('rx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('rx_packets', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tx_packets', sa.BigInteger(), nullable=False, server_default='0'),

        # Error counters
        sa.Column('rx_errors', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tx_errors', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rx_discards', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tx_discards', sa.Integer(), nullable=False, server_default='0'),

        # Calculated rates (bits per second)
        sa.Column('rx_rate_bps', sa.BigInteger(), nullable=True),
        sa.Column('tx_rate_bps', sa.BigInteger(), nullable=True),

        # Interface status
        sa.Column('oper_status', sa.String(20), nullable=False, server_default='unknown'),
        sa.Column('admin_status', sa.String(20), nullable=False, server_default='unknown'),
        sa.Column('speed_bps', sa.BigInteger(), nullable=True),
    )
    op.create_index('ix_interface_metrics_router_if_ts', 'interface_metrics',
                    ['router_id', 'interface_index', 'timestamp'])

    # =========================================================================
    # INTERFACE STATES (current snapshot for quick lookups)
    # =========================================================================
    op.create_table(
        'interface_states',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('router_id', sa.Integer(), sa.ForeignKey('routers.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('interface_index', sa.Integer(), nullable=False),
        sa.Column('interface_name', sa.String(100), nullable=False),
        sa.Column('interface_alias', sa.String(255), nullable=True),
        sa.Column('interface_type', sa.String(50), nullable=True),

        # Current state
        sa.Column('oper_status', sa.String(20), nullable=False, server_default='unknown'),
        sa.Column('admin_status', sa.String(20), nullable=False, server_default='unknown'),
        sa.Column('speed_bps', sa.BigInteger(), nullable=True),
        sa.Column('mtu', sa.Integer(), nullable=True),
        sa.Column('mac_address', sa.String(20), nullable=True),

        # Latest counters
        sa.Column('last_rx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('last_tx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('last_rx_rate_bps', sa.BigInteger(), nullable=True),
        sa.Column('last_tx_rate_bps', sa.BigInteger(), nullable=True),

        # State tracking
        sa.Column('last_state_change_at', sa.DateTime(), nullable=True),
        sa.Column('last_polled_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),

        # Is this an uplink/WAN interface?
        sa.Column('is_uplink', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.create_index('ix_interface_states_router_if', 'interface_states',
                    ['router_id', 'interface_index'], unique=True)

    # =========================================================================
    # INTERFACE METRIC ROLLUPS (aggregated for historical graphs)
    # =========================================================================
    op.create_table(
        'interface_metric_rollups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('router_id', sa.Integer(), sa.ForeignKey('routers.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('interface_index', sa.Integer(), nullable=False),
        sa.Column('aggregation', sa.String(20), nullable=False, index=True),  # hourly, daily, monthly
        sa.Column('period_start', sa.DateTime(), nullable=False, index=True),

        # Aggregated traffic rates (bps)
        sa.Column('avg_rx_rate_bps', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('avg_tx_rate_bps', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('max_rx_rate_bps', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('max_tx_rate_bps', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('min_rx_rate_bps', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('min_tx_rate_bps', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('p95_rx_rate_bps', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('p95_tx_rate_bps', sa.BigInteger(), nullable=False, server_default='0'),

        # Totals for the period
        sa.Column('total_rx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_tx_bytes', sa.BigInteger(), nullable=False, server_default='0'),

        # Error counts
        sa.Column('total_rx_errors', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tx_errors', sa.Integer(), nullable=False, server_default='0'),

        # Availability
        sa.Column('samples_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('uptime_percent', sa.Float(), nullable=False, server_default='100.0'),
    )
    op.create_index('ix_metric_rollup_lookup', 'interface_metric_rollups',
                    ['router_id', 'interface_index', 'aggregation', 'period_start'], unique=True)

    # =========================================================================
    # SUBSCRIPTION USAGE METRICS (daily aggregation from RADIUS)
    # =========================================================================
    op.create_table(
        'subscription_usage_metrics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('subscription_id', sa.Integer(),
                  sa.ForeignKey('subscriptions.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('period_date', sa.Date(), nullable=False, index=True),

        # Usage totals
        sa.Column('download_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('upload_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_bytes', sa.BigInteger(), nullable=False, server_default='0'),

        # Session stats
        sa.Column('session_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('session_duration_seconds', sa.Integer(), nullable=False, server_default='0'),

        # Peak rates
        sa.Column('peak_download_bps', sa.BigInteger(), nullable=True),
        sa.Column('peak_upload_bps', sa.BigInteger(), nullable=True),

        # Average rates
        sa.Column('avg_download_bps', sa.BigInteger(), nullable=True),
        sa.Column('avg_upload_bps', sa.BigInteger(), nullable=True),
    )
    op.create_index('ix_sub_usage_lookup', 'subscription_usage_metrics',
                    ['subscription_id', 'period_date'], unique=True)


def downgrade() -> None:
    # Drop in reverse order
    op.drop_index('ix_sub_usage_lookup', table_name='subscription_usage_metrics')
    op.drop_table('subscription_usage_metrics')

    op.drop_index('ix_metric_rollup_lookup', table_name='interface_metric_rollups')
    op.drop_table('interface_metric_rollups')

    op.drop_index('ix_interface_states_router_if', table_name='interface_states')
    op.drop_table('interface_states')

    op.drop_index('ix_interface_metrics_router_if_ts', table_name='interface_metrics')
    op.drop_table('interface_metrics')

    op.drop_index('ix_device_metrics_router_timestamp', table_name='device_metrics')
    op.drop_table('device_metrics')

    op.drop_table('snmp_polling_configs')
