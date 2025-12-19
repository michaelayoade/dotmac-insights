"""Add outbound sync columns and OutboundSyncLog table

Revision ID: 20251218_add_outbound_sync
Revises: 20251218_merge_fk_cleanup
Create Date: 2025-12-18

Adds sync_hash columns to unified_contacts for idempotency checking,
and creates outbound_sync_log table for audit trail.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251218_add_outbound_sync"
down_revision = "20251218_merge_fk_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sync hash columns to unified_contacts
    op.add_column(
        "unified_contacts",
        sa.Column("splynx_sync_hash", sa.String(64), nullable=True)
    )
    op.add_column(
        "unified_contacts",
        sa.Column("erpnext_sync_hash", sa.String(64), nullable=True)
    )
    op.add_column(
        "unified_contacts",
        sa.Column("last_synced_to_splynx", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "unified_contacts",
        sa.Column("last_synced_to_erpnext", sa.DateTime(), nullable=True)
    )

    # Create outbound_sync_log table
    op.create_table(
        "outbound_sync_log",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("entity_type", sa.String(50), nullable=False, index=True),
        sa.Column("entity_id", sa.Integer(), nullable=False, index=True),
        sa.Column("target_system", sa.String(50), nullable=False, index=True),  # splynx, erpnext
        sa.Column("operation", sa.String(20), nullable=False),  # create, update, delete
        sa.Column("idempotency_key", sa.String(255), nullable=True, unique=True),
        sa.Column("payload_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),  # pending, success, failed, skipped
        sa.Column("external_id", sa.String(255), nullable=True),  # ID in target system
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    # Create indexes for common queries
    op.create_index(
        "ix_outbound_sync_log_entity",
        "outbound_sync_log",
        ["entity_type", "entity_id"]
    )
    op.create_index(
        "ix_outbound_sync_log_pending",
        "outbound_sync_log",
        ["status", "next_retry_at"],
        postgresql_where=sa.text("status IN ('pending', 'failed')")
    )


def downgrade() -> None:
    op.drop_index("ix_outbound_sync_log_pending", table_name="outbound_sync_log")
    op.drop_index("ix_outbound_sync_log_entity", table_name="outbound_sync_log")
    op.drop_table("outbound_sync_log")

    op.drop_column("unified_contacts", "last_synced_to_erpnext")
    op.drop_column("unified_contacts", "last_synced_to_splynx")
    op.drop_column("unified_contacts", "erpnext_sync_hash")
    op.drop_column("unified_contacts", "splynx_sync_hash")
