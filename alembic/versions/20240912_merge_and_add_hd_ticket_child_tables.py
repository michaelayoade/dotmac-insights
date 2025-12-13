"""Merge heads and add HD Ticket child tables.

Revision ID: 20240912_hd_ticket_children
Revises: 20240911_purchase_invoice_audit_writeback, d3e4f5g6h7i8
Create Date: 2025-12-12

Adds:
- hd_ticket_comments table for HD Ticket Comment child table
- hd_ticket_activities table for HD Ticket Activity child table
- ticket_communications table for Communication doctype linked to tickets
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20240912_hd_ticket_children"
down_revision: Union[str, Sequence[str], None] = (
    "20240911_purchase_invoice_audit_writeback",
    "d3e4f5g6h7i8",
    "i4j5k6l7m8n9",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create hd_ticket_comments table
    op.create_table(
        "hd_ticket_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("erpnext_name", sa.String(255), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("comment_type", sa.String(50), nullable=True),
        sa.Column("commented_by", sa.String(255), nullable=True),
        sa.Column("commented_by_name", sa.String(255), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("comment_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_hd_ticket_comments_id", "hd_ticket_comments", ["id"])
    op.create_index("ix_hd_ticket_comments_ticket_id", "hd_ticket_comments", ["ticket_id"])
    op.create_index("ix_hd_ticket_comments_erpnext_name", "hd_ticket_comments", ["erpnext_name"])
    op.create_index("ix_hd_ticket_comments_comment_date", "hd_ticket_comments", ["comment_date"])

    # Create hd_ticket_activities table
    op.create_table(
        "hd_ticket_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("erpnext_name", sa.String(255), nullable=True),
        sa.Column("activity_type", sa.String(100), nullable=True),
        sa.Column("activity", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(255), nullable=True),
        sa.Column("from_status", sa.String(100), nullable=True),
        sa.Column("to_status", sa.String(100), nullable=True),
        sa.Column("activity_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_hd_ticket_activities_id", "hd_ticket_activities", ["id"])
    op.create_index("ix_hd_ticket_activities_ticket_id", "hd_ticket_activities", ["ticket_id"])
    op.create_index("ix_hd_ticket_activities_erpnext_name", "hd_ticket_activities", ["erpnext_name"])
    op.create_index("ix_hd_ticket_activities_activity_date", "hd_ticket_activities", ["activity_date"])

    # Create ticket_communications table
    op.create_table(
        "ticket_communications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("erpnext_id", sa.String(255), nullable=True),
        sa.Column("communication_type", sa.String(50), nullable=True),
        sa.Column("communication_medium", sa.String(50), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("sender", sa.String(255), nullable=True),
        sa.Column("sender_full_name", sa.String(255), nullable=True),
        sa.Column("recipients", sa.Text(), nullable=True),
        sa.Column("cc", sa.Text(), nullable=True),
        sa.Column("bcc", sa.Text(), nullable=True),
        sa.Column("sent_or_received", sa.String(20), nullable=True),
        sa.Column("read_receipt", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("delivery_status", sa.String(50), nullable=True),
        sa.Column("communication_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_ticket_communications_id", "ticket_communications", ["id"])
    op.create_index("ix_ticket_communications_ticket_id", "ticket_communications", ["ticket_id"])
    op.create_index("ix_ticket_communications_erpnext_id", "ticket_communications", ["erpnext_id"], unique=True)
    op.create_index("ix_ticket_communications_communication_date", "ticket_communications", ["communication_date"])


def downgrade() -> None:
    # Drop ticket_communications
    op.drop_index("ix_ticket_communications_communication_date", table_name="ticket_communications")
    op.drop_index("ix_ticket_communications_erpnext_id", table_name="ticket_communications")
    op.drop_index("ix_ticket_communications_ticket_id", table_name="ticket_communications")
    op.drop_index("ix_ticket_communications_id", table_name="ticket_communications")
    op.drop_table("ticket_communications")

    # Drop hd_ticket_activities
    op.drop_index("ix_hd_ticket_activities_activity_date", table_name="hd_ticket_activities")
    op.drop_index("ix_hd_ticket_activities_erpnext_name", table_name="hd_ticket_activities")
    op.drop_index("ix_hd_ticket_activities_ticket_id", table_name="hd_ticket_activities")
    op.drop_index("ix_hd_ticket_activities_id", table_name="hd_ticket_activities")
    op.drop_table("hd_ticket_activities")

    # Drop hd_ticket_comments
    op.drop_index("ix_hd_ticket_comments_comment_date", table_name="hd_ticket_comments")
    op.drop_index("ix_hd_ticket_comments_erpnext_name", table_name="hd_ticket_comments")
    op.drop_index("ix_hd_ticket_comments_ticket_id", table_name="hd_ticket_comments")
    op.drop_index("ix_hd_ticket_comments_id", table_name="hd_ticket_comments")
    op.drop_table("hd_ticket_comments")
