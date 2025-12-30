"""Add inventory:write permission and attach to admin role."""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20240906_inventory_write"
down_revision = "g2h3i4j5k6l7"
branch_labels = None
depends_on = None


def upgrade():
    # Create permission if missing
    op.execute(
        """
        INSERT INTO permissions (scope, description, category, created_at)
        SELECT 'inventory:write', 'Create/update/delete inventory data', 'inventory', NOW()
        WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE scope = 'inventory:write');
        """
    )

    # Attach to admin role if it exists
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT r.id, p.id, NOW()
        FROM roles r
        JOIN permissions p ON p.scope = 'inventory:write'
        WHERE r.name = 'admin'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          );
        """
    )


def downgrade():
    # Remove mapping from admin
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (SELECT id FROM permissions WHERE scope = 'inventory:write');
        """
    )
    # Remove permission
    op.execute("DELETE FROM permissions WHERE scope = 'inventory:write';")
