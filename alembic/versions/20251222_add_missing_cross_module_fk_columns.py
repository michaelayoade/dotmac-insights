"""Add missing cross-module FK columns for existing tables.

Revision ID: 20251222_add_missing_cross_module_fk_columns
Revises: 20251221_rename_company_to_dotmac_technologies
Create Date: 2025-12-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20251222_add_missing_cross_module_fk_columns"
down_revision: Union[str, None] = "20251221_rename_company_to_dotmac_technologies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ensure FK columns exist when tables are present."""
    bind = op.get_bind()
    inspector = inspect(bind)

    def has_table(table: str) -> bool:
        return inspector.has_table(table)

    def has_column(table: str, column: str) -> bool:
        if not has_table(table):
            return False
        return any(col["name"] == column for col in inspector.get_columns(table))

    def has_index(table: str, index_name: str) -> bool:
        if not has_table(table):
            return False
        return any(idx["name"] == index_name for idx in inspector.get_indexes(table))

    def has_fk(table: str, fk_name: str) -> bool:
        if not has_table(table):
            return False
        return any(fk["name"] == fk_name for fk in inspector.get_foreign_keys(table))

    # Journal entry items/accounts → accounts
    if has_table("journal_entry_items") and has_table("accounts") and not has_column("journal_entry_items", "account_id"):
        op.add_column("journal_entry_items", sa.Column("account_id", sa.Integer(), nullable=True))
        if not has_index("journal_entry_items", "ix_journal_entry_items_account_id"):
            op.create_index("ix_journal_entry_items_account_id", "journal_entry_items", ["account_id"])
        if not has_fk("journal_entry_items", "fk_journal_entry_items_account_id_accounts"):
            op.create_foreign_key(
                "fk_journal_entry_items_account_id_accounts",
                "journal_entry_items",
                "accounts",
                ["account_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if has_table("journal_entry_accounts") and has_table("accounts") and not has_column("journal_entry_accounts", "account_id"):
        op.add_column("journal_entry_accounts", sa.Column("account_id", sa.Integer(), nullable=True))
        if not has_index("journal_entry_accounts", "ix_journal_entry_accounts_account_id"):
            op.create_index("ix_journal_entry_accounts_account_id", "journal_entry_accounts", ["account_id"])
        if not has_fk("journal_entry_accounts", "fk_journal_entry_accounts_account_id_accounts"):
            op.create_foreign_key(
                "fk_journal_entry_accounts_account_id_accounts",
                "journal_entry_accounts",
                "accounts",
                ["account_id"],
                ["id"],
                ondelete="SET NULL",
            )

    # Suppliers → supplier_groups
    if has_table("suppliers") and has_table("supplier_groups") and not has_column("suppliers", "supplier_group_id"):
        op.add_column("suppliers", sa.Column("supplier_group_id", sa.Integer(), nullable=True))
        if not has_index("suppliers", "ix_suppliers_supplier_group_id"):
            op.create_index("ix_suppliers_supplier_group_id", "suppliers", ["supplier_group_id"])
        if not has_fk("suppliers", "fk_suppliers_supplier_group_id_supplier_groups"):
            op.create_foreign_key(
                "fk_suppliers_supplier_group_id_supplier_groups",
                "suppliers",
                "supplier_groups",
                ["supplier_group_id"],
                ["id"],
                ondelete="SET NULL",
            )

    # Purchase orders → cost_centers, projects
    if has_table("purchase_orders"):
        if has_table("cost_centers") and not has_column("purchase_orders", "cost_center_id"):
            op.add_column("purchase_orders", sa.Column("cost_center_id", sa.Integer(), nullable=True))
            if not has_index("purchase_orders", "ix_purchase_orders_cost_center_id"):
                op.create_index("ix_purchase_orders_cost_center_id", "purchase_orders", ["cost_center_id"])
            if not has_fk("purchase_orders", "fk_purchase_orders_cost_center_id_cost_centers"):
                op.create_foreign_key(
                    "fk_purchase_orders_cost_center_id_cost_centers",
                    "purchase_orders",
                    "cost_centers",
                    ["cost_center_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

        if has_table("projects") and not has_column("purchase_orders", "project_id"):
            op.add_column("purchase_orders", sa.Column("project_id", sa.Integer(), nullable=True))
            if not has_index("purchase_orders", "ix_purchase_orders_project_id"):
                op.create_index("ix_purchase_orders_project_id", "purchase_orders", ["project_id"])
            if not has_fk("purchase_orders", "fk_purchase_orders_project_id_projects"):
                op.create_foreign_key(
                    "fk_purchase_orders_project_id_projects",
                    "purchase_orders",
                    "projects",
                    ["project_id"],
                    ["id"],
                    ondelete="SET NULL",
                )


def downgrade() -> None:
    """No-op: safe migration to add missing columns only."""
    pass
