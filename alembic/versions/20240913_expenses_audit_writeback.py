"""Add audit, soft delete, and write-back fields to expenses."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240913_expenses_audit_writeback"
down_revision = "20240912_purchase_orders_debit_notes_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("expenses", sa.Column("origin_system", sa.String(length=50), nullable=False, server_default="external"))
    op.add_column("expenses", sa.Column("write_back_status", sa.String(length=50), nullable=False, server_default="synced"))
    op.add_column("expenses", sa.Column("write_back_error", sa.Text(), nullable=True))
    op.add_column("expenses", sa.Column("write_back_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("expenses", sa.Column("created_by_id", sa.Integer(), nullable=True))
    op.add_column("expenses", sa.Column("updated_by_id", sa.Integer(), nullable=True))
    op.add_column("expenses", sa.Column("deleted_by_id", sa.Integer(), nullable=True))
    op.add_column("expenses", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("expenses", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE expenses SET origin_system = 'external', write_back_status = 'synced' WHERE origin_system IS NULL")


def downgrade():
    op.drop_column("expenses", "is_deleted")
    op.drop_column("expenses", "deleted_at")
    op.drop_column("expenses", "deleted_by_id")
    op.drop_column("expenses", "updated_by_id")
    op.drop_column("expenses", "created_by_id")
    op.drop_column("expenses", "write_back_attempted_at")
    op.drop_column("expenses", "write_back_error")
    op.drop_column("expenses", "write_back_status")
    op.drop_column("expenses", "origin_system")
