"""Add audit, soft delete, and write-back fields to inventory tables."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240907_inventory_audit_writeback"
down_revision = "20240906_inventory_write"
branch_labels = None
depends_on = None


def upgrade():
    # Items
    op.add_column("items", sa.Column("origin_system", sa.String(length=50), nullable=False, server_default="external"))
    op.add_column("items", sa.Column("write_back_status", sa.String(length=50), nullable=False, server_default="synced"))
    op.add_column("items", sa.Column("write_back_error", sa.Text(), nullable=True))
    op.add_column("items", sa.Column("write_back_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("items", sa.Column("created_by_id", sa.Integer(), nullable=True))
    op.add_column("items", sa.Column("updated_by_id", sa.Integer(), nullable=True))
    op.add_column("items", sa.Column("deleted_by_id", sa.Integer(), nullable=True))
    op.add_column("items", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("items", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE items SET origin_system = 'external', write_back_status = 'synced' WHERE origin_system IS NULL")

    # Warehouses
    op.add_column("warehouses", sa.Column("origin_system", sa.String(length=50), nullable=False, server_default="external"))
    op.add_column("warehouses", sa.Column("write_back_status", sa.String(length=50), nullable=False, server_default="synced"))
    op.add_column("warehouses", sa.Column("write_back_error", sa.Text(), nullable=True))
    op.add_column("warehouses", sa.Column("write_back_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("warehouses", sa.Column("created_by_id", sa.Integer(), nullable=True))
    op.add_column("warehouses", sa.Column("updated_by_id", sa.Integer(), nullable=True))
    op.add_column("warehouses", sa.Column("deleted_by_id", sa.Integer(), nullable=True))
    op.add_column("warehouses", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("warehouses", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE warehouses SET origin_system = 'external', write_back_status = 'synced' WHERE origin_system IS NULL")

    # Stock entries
    op.add_column("stock_entries", sa.Column("origin_system", sa.String(length=50), nullable=False, server_default="external"))
    op.add_column("stock_entries", sa.Column("write_back_status", sa.String(length=50), nullable=False, server_default="synced"))
    op.add_column("stock_entries", sa.Column("write_back_error", sa.Text(), nullable=True))
    op.add_column("stock_entries", sa.Column("write_back_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stock_entries", sa.Column("created_by_id", sa.Integer(), nullable=True))
    op.add_column("stock_entries", sa.Column("updated_by_id", sa.Integer(), nullable=True))
    op.add_column("stock_entries", sa.Column("deleted_by_id", sa.Integer(), nullable=True))
    op.add_column("stock_entries", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stock_entries", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE stock_entries SET origin_system = 'external', write_back_status = 'synced' WHERE origin_system IS NULL")


def downgrade():
    op.drop_column("stock_entries", "is_deleted")
    op.drop_column("stock_entries", "deleted_at")
    op.drop_column("stock_entries", "deleted_by_id")
    op.drop_column("stock_entries", "updated_by_id")
    op.drop_column("stock_entries", "created_by_id")
    op.drop_column("stock_entries", "write_back_attempted_at")
    op.drop_column("stock_entries", "write_back_error")
    op.drop_column("stock_entries", "write_back_status")
    op.drop_column("stock_entries", "origin_system")

    op.drop_column("warehouses", "is_deleted")
    op.drop_column("warehouses", "deleted_at")
    op.drop_column("warehouses", "deleted_by_id")
    op.drop_column("warehouses", "updated_by_id")
    op.drop_column("warehouses", "created_by_id")
    op.drop_column("warehouses", "write_back_attempted_at")
    op.drop_column("warehouses", "write_back_error")
    op.drop_column("warehouses", "write_back_status")
    op.drop_column("warehouses", "origin_system")

    op.drop_column("items", "is_deleted")
    op.drop_column("items", "deleted_at")
    op.drop_column("items", "deleted_by_id")
    op.drop_column("items", "updated_by_id")
    op.drop_column("items", "created_by_id")
    op.drop_column("items", "write_back_attempted_at")
    op.drop_column("items", "write_back_error")
    op.drop_column("items", "write_back_status")
    op.drop_column("items", "origin_system")
