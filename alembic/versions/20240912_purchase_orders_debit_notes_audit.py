"""Add audit, soft delete, and write-back fields to purchase_orders and debit_notes."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240912_purchase_orders_debit_notes_audit"
down_revision = "20240911_purchase_invoice_audit_writeback"
branch_labels = None
depends_on = None


def _add_common(table: str):
    op.add_column(table, sa.Column("origin_system", sa.String(length=50), nullable=False, server_default="external"))
    op.add_column(table, sa.Column("write_back_status", sa.String(length=50), nullable=False, server_default="synced"))
    op.add_column(table, sa.Column("write_back_error", sa.Text(), nullable=True))
    op.add_column(table, sa.Column("write_back_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("created_by_id", sa.Integer(), nullable=True))
    op.add_column(table, sa.Column("updated_by_id", sa.Integer(), nullable=True))
    op.add_column(table, sa.Column("deleted_by_id", sa.Integer(), nullable=True))
    op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute(f"UPDATE {table} SET origin_system = 'external', write_back_status = 'synced' WHERE origin_system IS NULL")


def upgrade():
    _add_common("purchase_orders")
    _add_common("debit_notes")


def downgrade():
    for table in ("debit_notes", "purchase_orders"):
        op.drop_column(table, "is_deleted")
        op.drop_column(table, "deleted_at")
        op.drop_column(table, "deleted_by_id")
        op.drop_column(table, "updated_by_id")
        op.drop_column(table, "created_by_id")
        op.drop_column(table, "write_back_attempted_at")
        op.drop_column(table, "write_back_error")
        op.drop_column(table, "write_back_status")
        op.drop_column(table, "origin_system")
