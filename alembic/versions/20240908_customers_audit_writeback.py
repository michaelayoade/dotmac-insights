"""Add audit, soft delete, and write-back fields to customers."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240908_customers_audit_writeback"
down_revision = "20240907_inventory_audit_writeback"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customers", sa.Column("origin_system", sa.String(length=50), nullable=False, server_default="external"))
    op.add_column("customers", sa.Column("write_back_status", sa.String(length=50), nullable=False, server_default="synced"))
    op.add_column("customers", sa.Column("write_back_error", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("write_back_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customers", sa.Column("created_by_id", sa.Integer(), nullable=True))
    op.add_column("customers", sa.Column("updated_by_id", sa.Integer(), nullable=True))
    op.add_column("customers", sa.Column("deleted_by_id", sa.Integer(), nullable=True))
    op.add_column("customers", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customers", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE customers SET origin_system = 'external', write_back_status = 'synced' WHERE origin_system IS NULL")

    # Add write scope
    op.execute(
        """
        INSERT INTO permissions (scope, description, category, created_at)
        SELECT 'customers:write', 'Create/update/delete customers', 'customers', NOW()
        WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE scope = 'customers:write');
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT r.id, p.id, NOW()
        FROM roles r
        JOIN permissions p ON p.scope = 'customers:write'
        WHERE r.name = 'admin'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          );
        """
    )


def downgrade():
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE scope = 'customers:write')"
    )
    op.execute("DELETE FROM permissions WHERE scope = 'customers:write'")
    op.drop_column("customers", "is_deleted")
    op.drop_column("customers", "deleted_at")
    op.drop_column("customers", "deleted_by_id")
    op.drop_column("customers", "updated_by_id")
    op.drop_column("customers", "created_by_id")
    op.drop_column("customers", "write_back_attempted_at")
    op.drop_column("customers", "write_back_error")
    op.drop_column("customers", "write_back_status")
    op.drop_column("customers", "origin_system")
