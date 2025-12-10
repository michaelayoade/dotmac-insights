"""Add indexes to support analytics queries

Revision ID: 7a3a6ab2d8df
Revises: f5545281ad87
Create Date: 2026-01-05 10:00:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7a3a6ab2d8df"
down_revision: Union[str, None] = "f5545281ad87"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_tickets_priority", "tickets", ["priority"])
    op.create_index("ix_sales_orders_status", "sales_orders", ["status"])
    op.create_index("ix_quotations_status", "quotations", ["status"])
    op.create_index("ix_quotations_territory", "quotations", ["territory"])
    op.create_index("ix_network_monitors_ping_state", "network_monitors", ["ping_state"])
    op.create_index("ix_purchase_invoices_status", "purchase_invoices", ["status"])


def downgrade() -> None:
    op.drop_index("ix_purchase_invoices_status", table_name="purchase_invoices")
    op.drop_index("ix_network_monitors_ping_state", table_name="network_monitors")
    op.drop_index("ix_quotations_territory", table_name="quotations")
    op.drop_index("ix_quotations_status", table_name="quotations")
    op.drop_index("ix_sales_orders_status", table_name="sales_orders")
    op.drop_index("ix_tickets_priority", table_name="tickets")
