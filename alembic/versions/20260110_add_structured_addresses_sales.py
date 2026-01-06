"""Add structured addresses to sales orders and quotations.

Revision ID: 20260110_add_structured_addresses_sales
Revises: ef390db26fdd
Create Date: 2026-01-10 12:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260110_add_structured_addresses_sales"
down_revision: Union[str, Sequence[str], None] = "ef390db26fdd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sales_orders", sa.Column("billing_address_line1", sa.String(length=255), nullable=True))
    op.add_column("sales_orders", sa.Column("billing_address_line2", sa.String(length=255), nullable=True))
    op.add_column("sales_orders", sa.Column("billing_city", sa.String(length=100), nullable=True))
    op.add_column("sales_orders", sa.Column("billing_state", sa.String(length=100), nullable=True))
    op.add_column("sales_orders", sa.Column("billing_postal_code", sa.String(length=20), nullable=True))
    op.add_column("sales_orders", sa.Column("billing_country", sa.String(length=100), nullable=True))
    op.add_column("sales_orders", sa.Column("billing_gps_lat", sa.Numeric(10, 6), nullable=True))
    op.add_column("sales_orders", sa.Column("billing_gps_lng", sa.Numeric(10, 6), nullable=True))
    op.add_column("sales_orders", sa.Column("shipping_address_line1", sa.String(length=255), nullable=True))
    op.add_column("sales_orders", sa.Column("shipping_address_line2", sa.String(length=255), nullable=True))
    op.add_column("sales_orders", sa.Column("shipping_city", sa.String(length=100), nullable=True))
    op.add_column("sales_orders", sa.Column("shipping_state", sa.String(length=100), nullable=True))
    op.add_column("sales_orders", sa.Column("shipping_postal_code", sa.String(length=20), nullable=True))
    op.add_column("sales_orders", sa.Column("shipping_country", sa.String(length=100), nullable=True))
    op.add_column("sales_orders", sa.Column("shipping_gps_lat", sa.Numeric(10, 6), nullable=True))
    op.add_column("sales_orders", sa.Column("shipping_gps_lng", sa.Numeric(10, 6), nullable=True))

    op.add_column("quotations", sa.Column("billing_address_line1", sa.String(length=255), nullable=True))
    op.add_column("quotations", sa.Column("billing_address_line2", sa.String(length=255), nullable=True))
    op.add_column("quotations", sa.Column("billing_city", sa.String(length=100), nullable=True))
    op.add_column("quotations", sa.Column("billing_state", sa.String(length=100), nullable=True))
    op.add_column("quotations", sa.Column("billing_postal_code", sa.String(length=20), nullable=True))
    op.add_column("quotations", sa.Column("billing_country", sa.String(length=100), nullable=True))
    op.add_column("quotations", sa.Column("billing_gps_lat", sa.Numeric(10, 6), nullable=True))
    op.add_column("quotations", sa.Column("billing_gps_lng", sa.Numeric(10, 6), nullable=True))
    op.add_column("quotations", sa.Column("shipping_address_line1", sa.String(length=255), nullable=True))
    op.add_column("quotations", sa.Column("shipping_address_line2", sa.String(length=255), nullable=True))
    op.add_column("quotations", sa.Column("shipping_city", sa.String(length=100), nullable=True))
    op.add_column("quotations", sa.Column("shipping_state", sa.String(length=100), nullable=True))
    op.add_column("quotations", sa.Column("shipping_postal_code", sa.String(length=20), nullable=True))
    op.add_column("quotations", sa.Column("shipping_country", sa.String(length=100), nullable=True))
    op.add_column("quotations", sa.Column("shipping_gps_lat", sa.Numeric(10, 6), nullable=True))
    op.add_column("quotations", sa.Column("shipping_gps_lng", sa.Numeric(10, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("quotations", "shipping_gps_lng")
    op.drop_column("quotations", "shipping_gps_lat")
    op.drop_column("quotations", "shipping_country")
    op.drop_column("quotations", "shipping_postal_code")
    op.drop_column("quotations", "shipping_state")
    op.drop_column("quotations", "shipping_city")
    op.drop_column("quotations", "shipping_address_line2")
    op.drop_column("quotations", "shipping_address_line1")
    op.drop_column("quotations", "billing_gps_lng")
    op.drop_column("quotations", "billing_gps_lat")
    op.drop_column("quotations", "billing_country")
    op.drop_column("quotations", "billing_postal_code")
    op.drop_column("quotations", "billing_state")
    op.drop_column("quotations", "billing_city")
    op.drop_column("quotations", "billing_address_line2")
    op.drop_column("quotations", "billing_address_line1")

    op.drop_column("sales_orders", "shipping_gps_lng")
    op.drop_column("sales_orders", "shipping_gps_lat")
    op.drop_column("sales_orders", "shipping_country")
    op.drop_column("sales_orders", "shipping_postal_code")
    op.drop_column("sales_orders", "shipping_state")
    op.drop_column("sales_orders", "shipping_city")
    op.drop_column("sales_orders", "shipping_address_line2")
    op.drop_column("sales_orders", "shipping_address_line1")
    op.drop_column("sales_orders", "billing_gps_lng")
    op.drop_column("sales_orders", "billing_gps_lat")
    op.drop_column("sales_orders", "billing_country")
    op.drop_column("sales_orders", "billing_postal_code")
    op.drop_column("sales_orders", "billing_state")
    op.drop_column("sales_orders", "billing_city")
    op.drop_column("sales_orders", "billing_address_line2")
    op.drop_column("sales_orders", "billing_address_line1")
