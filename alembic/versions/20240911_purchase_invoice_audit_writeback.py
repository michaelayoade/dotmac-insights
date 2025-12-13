"""Add audit, soft delete, and write-back fields to purchase_invoices."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240911_purchase_invoice_audit_writeback"
down_revision = "20240910_sales_audit_writeback"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("purchase_invoices", sa.Column("origin_system", sa.String(length=50), nullable=False, server_default="external"))
    op.add_column("purchase_invoices", sa.Column("write_back_status", sa.String(length=50), nullable=False, server_default="synced"))
    op.add_column("purchase_invoices", sa.Column("write_back_error", sa.Text(), nullable=True))
    op.add_column("purchase_invoices", sa.Column("write_back_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("purchase_invoices", sa.Column("created_by_id", sa.Integer(), nullable=True))
    op.add_column("purchase_invoices", sa.Column("updated_by_id", sa.Integer(), nullable=True))
    op.add_column("purchase_invoices", sa.Column("deleted_by_id", sa.Integer(), nullable=True))
    op.add_column("purchase_invoices", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("purchase_invoices", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE purchase_invoices SET origin_system = 'external', write_back_status = 'synced' WHERE origin_system IS NULL")

    # Permission (if not already present)
    op.execute(
        """
        INSERT INTO permissions (scope, description, category, created_at)
        SELECT 'purchasing:write', 'Create/update/delete purchase invoices', 'purchasing', NOW()
        WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE scope = 'purchasing:write');
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT r.id, p.id, NOW()
        FROM roles r
        JOIN permissions p ON p.scope = 'purchasing:write'
        WHERE r.name = 'admin'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          );
        """
    )


def downgrade():
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE scope = 'purchasing:write')"
    )
    op.execute("DELETE FROM permissions WHERE scope = 'purchasing:write'")
    op.drop_column("purchase_invoices", "is_deleted")
    op.drop_column("purchase_invoices", "deleted_at")
    op.drop_column("purchase_invoices", "deleted_by_id")
    op.drop_column("purchase_invoices", "updated_by_id")
    op.drop_column("purchase_invoices", "created_by_id")
    op.drop_column("purchase_invoices", "write_back_attempted_at")
    op.drop_column("purchase_invoices", "write_back_error")
    op.drop_column("purchase_invoices", "write_back_status")
    op.drop_column("purchase_invoices", "origin_system")
