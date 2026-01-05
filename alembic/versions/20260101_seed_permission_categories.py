"""Seed permission categories for granular RBAC

Seeds initial permission categories and updates existing permissions
with category assignments for UI organization.

Revision ID: rbac_seed_001
Revises: rbac_granular_001
Create Date: 2026-01-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "rbac_seed_001"
down_revision: Union[str, None] = "rbac_granular_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Permission category definitions
PERMISSION_CATEGORIES = [
    {
        "name": "admin",
        "display_name": "Administration",
        "description": "User management, roles, system configuration",
        "icon": "settings",
        "display_order": 10,
    },
    {
        "name": "customers",
        "display_name": "Customer Management",
        "description": "Customer accounts, contacts, and related data",
        "icon": "users",
        "display_order": 20,
    },
    {
        "name": "support",
        "display_name": "Support & Helpdesk",
        "description": "Tickets, SLAs, knowledge base",
        "icon": "life-buoy",
        "display_order": 30,
    },
    {
        "name": "accounting",
        "display_name": "Accounting & Finance",
        "description": "Invoices, payments, ledger, reports",
        "icon": "dollar-sign",
        "display_order": 40,
    },
    {
        "name": "hr",
        "display_name": "Human Resources",
        "description": "Employees, payroll, leave, attendance",
        "icon": "briefcase",
        "display_order": 50,
    },
    {
        "name": "inventory",
        "display_name": "Inventory & Assets",
        "description": "Warehouses, stock, fixed assets",
        "icon": "package",
        "display_order": 60,
    },
    {
        "name": "network",
        "display_name": "Network Management",
        "description": "Routers, IPs, POPs, provisioning",
        "icon": "globe",
        "display_order": 70,
    },
    {
        "name": "sales",
        "display_name": "Sales & CRM",
        "description": "Opportunities, quotations, orders",
        "icon": "trending-up",
        "display_order": 80,
    },
    {
        "name": "purchasing",
        "display_name": "Purchasing",
        "description": "Suppliers, purchase orders, bills",
        "icon": "shopping-cart",
        "display_order": 90,
    },
    {
        "name": "projects",
        "display_name": "Projects",
        "description": "Projects, tasks, milestones",
        "icon": "folder",
        "display_order": 100,
    },
    {
        "name": "reports",
        "display_name": "Reports & Analytics",
        "description": "Financial reports, dashboards, insights",
        "icon": "bar-chart",
        "display_order": 110,
    },
    {
        "name": "sync",
        "display_name": "Data Synchronization",
        "description": "External system sync settings",
        "icon": "refresh-cw",
        "display_order": 120,
    },
    {
        "name": "settings",
        "display_name": "Settings",
        "description": "General system settings",
        "icon": "sliders",
        "display_order": 130,
    },
]

# Mapping of permission name prefixes to category names
PERMISSION_CATEGORY_MAPPING = {
    "admin:": "admin",
    "users:": "admin",
    "roles:": "admin",
    "tokens:": "admin",
    "customers:": "customers",
    "contacts:": "customers",
    "crm:": "sales",
    "opportunities:": "sales",
    "tickets:": "support",
    "support:": "support",
    "kb:": "support",
    "sla:": "support",
    "accounting:": "accounting",
    "invoices:": "accounting",
    "payments:": "accounting",
    "journal:": "accounting",
    "gl:": "accounting",
    "books:": "accounting",
    "hr:": "hr",
    "employees:": "hr",
    "leave:": "hr",
    "payroll:": "hr",
    "attendance:": "hr",
    "inventory:": "inventory",
    "assets:": "inventory",
    "warehouses:": "inventory",
    "stock:": "inventory",
    "network:": "network",
    "routers:": "network",
    "ips:": "network",
    "pops:": "network",
    "sales:": "sales",
    "quotations:": "sales",
    "orders:": "sales",
    "purchasing:": "purchasing",
    "suppliers:": "purchasing",
    "po:": "purchasing",
    "bills:": "purchasing",
    "projects:": "projects",
    "tasks:": "projects",
    "milestones:": "projects",
    "reports:": "reports",
    "analytics:": "reports",
    "dashboards:": "reports",
    "sync:": "sync",
    "settings:": "settings",
}


def upgrade() -> None:
    connection = op.get_bind()

    # Insert permission categories
    for cat in PERMISSION_CATEGORIES:
        connection.execute(
            sa.text("""
                INSERT INTO permission_categories (name, display_name, description, icon, display_order)
                VALUES (:name, :display_name, :description, :icon, :display_order)
                ON CONFLICT (name) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    description = EXCLUDED.description,
                    icon = EXCLUDED.icon,
                    display_order = EXCLUDED.display_order
            """),
            cat,
        )

    # Get category IDs
    result = connection.execute(
        sa.text("SELECT id, name FROM permission_categories")
    )
    category_ids = {row[1]: row[0] for row in result}

    # Get all permissions
    result = connection.execute(
        sa.text("SELECT id, scope FROM permissions")
    )
    permissions = list(result)

    # Update permissions with category_id
    for perm_id, perm_scope in permissions:
        category_name = None

        # Find matching category by prefix
        for prefix, cat_name in PERMISSION_CATEGORY_MAPPING.items():
            if perm_scope.startswith(prefix):
                category_name = cat_name
                break

        # If no prefix match, try to match on exact category field
        if not category_name:
            # Get current category string value
            current_cat = connection.execute(
                sa.text("SELECT category FROM permissions WHERE id = :id"),
                {"id": perm_id}
            ).scalar()

            if current_cat and current_cat.lower() in category_ids:
                category_name = current_cat.lower()

        if category_name and category_name in category_ids:
            connection.execute(
                sa.text("""
                    UPDATE permissions
                    SET category_id = :category_id
                    WHERE id = :id
                """),
                {"category_id": category_ids[category_name], "id": perm_id}
            )

    # Set display_name from description where not already set
    connection.execute(
        sa.text("""
            UPDATE permissions
            SET display_name = description
            WHERE display_name IS NULL AND description IS NOT NULL
        """)
    )


def downgrade() -> None:
    connection = op.get_bind()

    # Clear category_id from permissions
    connection.execute(
        sa.text("UPDATE permissions SET category_id = NULL")
    )

    # Delete all permission categories
    connection.execute(
        sa.text("DELETE FROM permission_categories")
    )
