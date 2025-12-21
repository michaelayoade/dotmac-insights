"""Add remaining cross-module FKs and create SupplierGroup model.

This migration completes the cross-module FK additions:
- JournalEntryItem: account_id → accounts (CRITICAL for GL integrity)
- Supplier: supplier_group_id → supplier_groups (new model)
- SalesOrder: sales_partner_id → sales_persons, territory_id → territories
- Quotation: sales_partner_id → sales_persons, territory_id → territories
- Opportunity: campaign_id → campaigns
- PurchaseOrder: cost_center_id → cost_centers, project_id → projects

Also creates the new SupplierGroup table for supplier categorization.

Revision ID: 20251221_add_remaining_cross_module_fks
Revises: 20251221_add_cross_module_fks
Create Date: 2025-12-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "20251221_add_remaining_cross_module_fks"
down_revision: Union[str, None] = "20251221_add_cross_module_fks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add remaining cross-module FK columns and create SupplierGroup table."""

    # ==========================================================================
    # Create SupplierGroup table (must be created BEFORE supplier FK)
    # ==========================================================================
    op.create_table(
        "supplier_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("erpnext_id", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parent_supplier_group", sa.String(255), nullable=True),
        sa.Column("parent_supplier_group_id", sa.Integer(), nullable=True),
        sa.Column("is_group", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("lft", sa.Integer(), nullable=True),
        sa.Column("rgt", sa.Integer(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("erpnext_id"),
        sa.UniqueConstraint("name"),
        sa.ForeignKeyConstraint(
            ["parent_supplier_group_id"],
            ["supplier_groups.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_supplier_groups_id", "supplier_groups", ["id"])
    op.create_index("ix_supplier_groups_erpnext_id", "supplier_groups", ["erpnext_id"])
    op.create_index("ix_supplier_groups_name", "supplier_groups", ["name"])
    op.create_index("ix_supplier_groups_parent_supplier_group_id", "supplier_groups", ["parent_supplier_group_id"])

    # ==========================================================================
    # JournalEntryItem: account_id → accounts (CRITICAL)
    # ==========================================================================
    op.add_column(
        "journal_entry_items",
        sa.Column("account_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_journal_entry_items_account_id", "journal_entry_items", ["account_id"])
    op.create_foreign_key(
        "fk_journal_entry_items_account_id_accounts",
        "journal_entry_items",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ==========================================================================
    # Supplier: supplier_group_id → supplier_groups
    # ==========================================================================
    op.add_column(
        "suppliers",
        sa.Column("supplier_group_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_suppliers_supplier_group_id", "suppliers", ["supplier_group_id"])
    op.create_foreign_key(
        "fk_suppliers_supplier_group_id_supplier_groups",
        "suppliers",
        "supplier_groups",
        ["supplier_group_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ==========================================================================
    # SalesOrder: sales_partner_id → sales_persons, territory_id → territories
    # ==========================================================================
    op.add_column(
        "sales_orders",
        sa.Column("sales_partner_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "sales_orders",
        sa.Column("territory_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_sales_orders_sales_partner_id", "sales_orders", ["sales_partner_id"])
    op.create_index("ix_sales_orders_territory_id", "sales_orders", ["territory_id"])
    op.create_foreign_key(
        "fk_sales_orders_sales_partner_id_sales_persons",
        "sales_orders",
        "sales_persons",
        ["sales_partner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_sales_orders_territory_id_territories",
        "sales_orders",
        "territories",
        ["territory_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ==========================================================================
    # Quotation: sales_partner_id → sales_persons, territory_id → territories
    # ==========================================================================
    op.add_column(
        "quotations",
        sa.Column("sales_partner_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "quotations",
        sa.Column("territory_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_quotations_sales_partner_id", "quotations", ["sales_partner_id"])
    op.create_index("ix_quotations_territory_id", "quotations", ["territory_id"])
    op.create_foreign_key(
        "fk_quotations_sales_partner_id_sales_persons",
        "quotations",
        "sales_persons",
        ["sales_partner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_quotations_territory_id_territories",
        "quotations",
        "territories",
        ["territory_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ==========================================================================
    # Opportunity: campaign_id → campaigns
    # ==========================================================================
    op.add_column(
        "opportunities",
        sa.Column("campaign_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_opportunities_campaign_id", "opportunities", ["campaign_id"])
    op.create_foreign_key(
        "fk_opportunities_campaign_id_campaigns",
        "opportunities",
        "campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ==========================================================================
    # PurchaseOrder: cost_center_id → cost_centers, project_id → projects
    # ==========================================================================
    op.add_column(
        "purchase_orders",
        sa.Column("cost_center_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("project_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_purchase_orders_cost_center_id", "purchase_orders", ["cost_center_id"])
    op.create_index("ix_purchase_orders_project_id", "purchase_orders", ["project_id"])
    op.create_foreign_key(
        "fk_purchase_orders_cost_center_id_cost_centers",
        "purchase_orders",
        "cost_centers",
        ["cost_center_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_purchase_orders_project_id_projects",
        "purchase_orders",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove cross-module FK columns and drop SupplierGroup table."""

    # PurchaseOrder
    op.drop_constraint("fk_purchase_orders_project_id_projects", "purchase_orders", type_="foreignkey")
    op.drop_constraint("fk_purchase_orders_cost_center_id_cost_centers", "purchase_orders", type_="foreignkey")
    op.drop_index("ix_purchase_orders_project_id", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_cost_center_id", table_name="purchase_orders")
    op.drop_column("purchase_orders", "project_id")
    op.drop_column("purchase_orders", "cost_center_id")

    # Opportunity
    op.drop_constraint("fk_opportunities_campaign_id_campaigns", "opportunities", type_="foreignkey")
    op.drop_index("ix_opportunities_campaign_id", table_name="opportunities")
    op.drop_column("opportunities", "campaign_id")

    # Quotation
    op.drop_constraint("fk_quotations_territory_id_territories", "quotations", type_="foreignkey")
    op.drop_constraint("fk_quotations_sales_partner_id_sales_persons", "quotations", type_="foreignkey")
    op.drop_index("ix_quotations_territory_id", table_name="quotations")
    op.drop_index("ix_quotations_sales_partner_id", table_name="quotations")
    op.drop_column("quotations", "territory_id")
    op.drop_column("quotations", "sales_partner_id")

    # SalesOrder
    op.drop_constraint("fk_sales_orders_territory_id_territories", "sales_orders", type_="foreignkey")
    op.drop_constraint("fk_sales_orders_sales_partner_id_sales_persons", "sales_orders", type_="foreignkey")
    op.drop_index("ix_sales_orders_territory_id", table_name="sales_orders")
    op.drop_index("ix_sales_orders_sales_partner_id", table_name="sales_orders")
    op.drop_column("sales_orders", "territory_id")
    op.drop_column("sales_orders", "sales_partner_id")

    # Supplier
    op.drop_constraint("fk_suppliers_supplier_group_id_supplier_groups", "suppliers", type_="foreignkey")
    op.drop_index("ix_suppliers_supplier_group_id", table_name="suppliers")
    op.drop_column("suppliers", "supplier_group_id")

    # JournalEntryItem
    op.drop_constraint("fk_journal_entry_items_account_id_accounts", "journal_entry_items", type_="foreignkey")
    op.drop_index("ix_journal_entry_items_account_id", table_name="journal_entry_items")
    op.drop_column("journal_entry_items", "account_id")

    # SupplierGroup table (drop last since supplier FK depends on it)
    op.drop_index("ix_supplier_groups_parent_supplier_group_id", table_name="supplier_groups")
    op.drop_index("ix_supplier_groups_name", table_name="supplier_groups")
    op.drop_index("ix_supplier_groups_erpnext_id", table_name="supplier_groups")
    op.drop_index("ix_supplier_groups_id", table_name="supplier_groups")
    op.drop_table("supplier_groups")
