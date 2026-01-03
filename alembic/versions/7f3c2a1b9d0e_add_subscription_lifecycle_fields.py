"""Add subscription lifecycle fields.

Adds fields to support full service lifecycle management:
- Extended lifecycle state
- Suspension tracking (reason, timestamp, count)
- Grace period management
- Termination tracking

Revision ID: 7f3c2a1b9d0e
Revises: f85bf5868197
Create Date: 2026-01-03
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f3c2a1b9d0e"
down_revision = "f85bf5868197"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add lifecycle state field (extended beyond basic status)
    op.add_column(
        "subscriptions",
        sa.Column("lifecycle_state", sa.String(50), nullable=True),
    )

    # Suspension tracking
    op.add_column(
        "subscriptions",
        sa.Column("suspension_reason", sa.String(50), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("suspended_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("suspended_by", sa.String(255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("suspension_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "subscriptions",
        sa.Column("suspension_notes", sa.Text(), nullable=True),
    )

    # Grace period tracking
    op.add_column(
        "subscriptions",
        sa.Column("grace_period_starts_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("grace_period_ends_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("grace_extensions_used", sa.Integer(), server_default="0", nullable=False),
    )

    # Termination tracking
    op.add_column(
        "subscriptions",
        sa.Column("termination_reason", sa.String(50), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("terminated_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("terminated_by", sa.String(255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("termination_notes", sa.Text(), nullable=True),
    )

    # Last lifecycle event tracking
    op.add_column(
        "subscriptions",
        sa.Column("last_lifecycle_action", sa.String(50), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("last_lifecycle_at", sa.DateTime(), nullable=True),
    )

    # Create indexes for common queries
    op.create_index(
        "ix_subscriptions_lifecycle_state",
        "subscriptions",
        ["lifecycle_state"],
    )
    op.create_index(
        "ix_subscriptions_suspension_reason",
        "subscriptions",
        ["suspension_reason"],
    )
    op.create_index(
        "ix_subscriptions_grace_period_ends_at",
        "subscriptions",
        ["grace_period_ends_at"],
    )
    op.create_index(
        "ix_subscriptions_suspended_at",
        "subscriptions",
        ["suspended_at"],
    )

    # Migrate existing status to lifecycle_state
    # Map: pending -> pending_activation, active -> active, suspended -> suspended, cancelled -> cancelled
    op.execute("""
        UPDATE subscriptions
        SET lifecycle_state = CASE
            WHEN status = 'PENDING' THEN 'pending_activation'
            WHEN status = 'ACTIVE' THEN 'active'
            WHEN status = 'SUSPENDED' THEN 'suspended'
            WHEN status = 'CANCELLED' THEN 'cancelled'
            ELSE 'pending_activation'
        END
        WHERE lifecycle_state IS NULL
    """)


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_subscriptions_suspended_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_grace_period_ends_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_suspension_reason", table_name="subscriptions")
    op.drop_index("ix_subscriptions_lifecycle_state", table_name="subscriptions")

    # Drop columns
    op.drop_column("subscriptions", "last_lifecycle_at")
    op.drop_column("subscriptions", "last_lifecycle_action")
    op.drop_column("subscriptions", "termination_notes")
    op.drop_column("subscriptions", "terminated_by")
    op.drop_column("subscriptions", "terminated_at")
    op.drop_column("subscriptions", "termination_reason")
    op.drop_column("subscriptions", "grace_extensions_used")
    op.drop_column("subscriptions", "grace_period_ends_at")
    op.drop_column("subscriptions", "grace_period_starts_at")
    op.drop_column("subscriptions", "suspension_notes")
    op.drop_column("subscriptions", "suspension_count")
    op.drop_column("subscriptions", "suspended_by")
    op.drop_column("subscriptions", "suspended_at")
    op.drop_column("subscriptions", "suspension_reason")
    op.drop_column("subscriptions", "lifecycle_state")
