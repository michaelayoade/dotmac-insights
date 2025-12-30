"""Backfill cross-module FK columns from legacy text fields.

Revision ID: 20251221_backfill_cross_module_fks
Revises: 20251221_add_remaining_cross_module_fks
Create Date: 2025-12-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20251221_backfill_cross_module_fks"
down_revision: Union[str, None] = "20251221_add_remaining_cross_module_fks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Populate new FK columns by matching existing text fields."""
    bind = op.get_bind()
    inspector = inspect(bind)

    def has_column(table: str, column: str) -> bool:
        if not inspector.has_table(table):
            return False
        return any(col["name"] == column for col in inspector.get_columns(table))

    # Supplier.supplier_group_id ← supplier_groups.name / erpnext_id
    if has_column("suppliers", "supplier_group_id") and inspector.has_table("supplier_groups"):
        op.execute(
            sa.text(
                """
                UPDATE suppliers AS s
                SET supplier_group_id = sg.id
                FROM supplier_groups AS sg
                WHERE s.supplier_group_id IS NULL
                  AND s.supplier_group IS NOT NULL
                  AND lower(s.supplier_group) = lower(sg.name)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE suppliers AS s
                SET supplier_group_id = sg.id
                FROM supplier_groups AS sg
                WHERE s.supplier_group_id IS NULL
                  AND s.supplier_group IS NOT NULL
                  AND sg.erpnext_id IS NOT NULL
                  AND lower(s.supplier_group) = lower(sg.erpnext_id)
                """
            )
        )

    # SalesOrder.sales_partner_id ← sales_persons.sales_person_name / erpnext_id
    if has_column("sales_orders", "sales_partner_id") and inspector.has_table("sales_persons"):
        op.execute(
            sa.text(
                """
                UPDATE sales_orders AS so
                SET sales_partner_id = sp.id
                FROM sales_persons AS sp
                WHERE so.sales_partner_id IS NULL
                  AND so.sales_partner IS NOT NULL
                  AND lower(so.sales_partner) = lower(sp.sales_person_name)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE sales_orders AS so
                SET sales_partner_id = sp.id
                FROM sales_persons AS sp
                WHERE so.sales_partner_id IS NULL
                  AND so.sales_partner IS NOT NULL
                  AND sp.erpnext_id IS NOT NULL
                  AND lower(so.sales_partner) = lower(sp.erpnext_id)
                """
            )
        )

    # SalesOrder.territory_id ← territories.territory_name / erpnext_id
    if has_column("sales_orders", "territory_id") and inspector.has_table("territories"):
        op.execute(
            sa.text(
                """
                UPDATE sales_orders AS so
                SET territory_id = t.id
                FROM territories AS t
                WHERE so.territory_id IS NULL
                  AND so.territory IS NOT NULL
                  AND lower(so.territory) = lower(t.territory_name)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE sales_orders AS so
                SET territory_id = t.id
                FROM territories AS t
                WHERE so.territory_id IS NULL
                  AND so.territory IS NOT NULL
                  AND t.erpnext_id IS NOT NULL
                  AND lower(so.territory) = lower(t.erpnext_id)
                """
            )
        )

    # Quotation.sales_partner_id ← sales_persons.sales_person_name / erpnext_id
    if has_column("quotations", "sales_partner_id") and inspector.has_table("sales_persons"):
        op.execute(
            sa.text(
                """
                UPDATE quotations AS q
                SET sales_partner_id = sp.id
                FROM sales_persons AS sp
                WHERE q.sales_partner_id IS NULL
                  AND q.sales_partner IS NOT NULL
                  AND lower(q.sales_partner) = lower(sp.sales_person_name)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE quotations AS q
                SET sales_partner_id = sp.id
                FROM sales_persons AS sp
                WHERE q.sales_partner_id IS NULL
                  AND q.sales_partner IS NOT NULL
                  AND sp.erpnext_id IS NOT NULL
                  AND lower(q.sales_partner) = lower(sp.erpnext_id)
                """
            )
        )

    # Quotation.territory_id ← territories.territory_name / erpnext_id
    if has_column("quotations", "territory_id") and inspector.has_table("territories"):
        op.execute(
            sa.text(
                """
                UPDATE quotations AS q
                SET territory_id = t.id
                FROM territories AS t
                WHERE q.territory_id IS NULL
                  AND q.territory IS NOT NULL
                  AND lower(q.territory) = lower(t.territory_name)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE quotations AS q
                SET territory_id = t.id
                FROM territories AS t
                WHERE q.territory_id IS NULL
                  AND q.territory IS NOT NULL
                  AND t.erpnext_id IS NOT NULL
                  AND lower(q.territory) = lower(t.erpnext_id)
                """
            )
        )

    # Opportunity.campaign_id ← campaigns.name / erpnext_id
    if has_column("opportunities", "campaign_id") and inspector.has_table("campaigns"):
        op.execute(
            sa.text(
                """
                UPDATE opportunities AS o
                SET campaign_id = c.id
                FROM campaigns AS c
                WHERE o.campaign_id IS NULL
                  AND o.campaign IS NOT NULL
                  AND lower(o.campaign) = lower(c.name)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE opportunities AS o
                SET campaign_id = c.id
                FROM campaigns AS c
                WHERE o.campaign_id IS NULL
                  AND o.campaign IS NOT NULL
                  AND c.erpnext_id IS NOT NULL
                  AND lower(o.campaign) = lower(c.erpnext_id)
                """
            )
        )

    # PurchaseOrder.cost_center_id ← cost_centers.cost_center_name / erpnext_id
    if has_column("purchase_orders", "cost_center_id") and inspector.has_table("cost_centers"):
        op.execute(
            sa.text(
                """
                UPDATE purchase_orders AS po
                SET cost_center_id = cc.id
                FROM cost_centers AS cc
                WHERE po.cost_center_id IS NULL
                  AND po.cost_center IS NOT NULL
                  AND lower(po.cost_center) = lower(cc.cost_center_name)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE purchase_orders AS po
                SET cost_center_id = cc.id
                FROM cost_centers AS cc
                WHERE po.cost_center_id IS NULL
                  AND po.cost_center IS NOT NULL
                  AND cc.erpnext_id IS NOT NULL
                  AND lower(po.cost_center) = lower(cc.erpnext_id)
                """
            )
        )

    # PurchaseOrder.project_id ← projects.project_name / erpnext_id
    if has_column("purchase_orders", "project_id") and inspector.has_table("projects"):
        op.execute(
            sa.text(
                """
                UPDATE purchase_orders AS po
                SET project_id = p.id
                FROM projects AS p
                WHERE po.project_id IS NULL
                  AND po.project IS NOT NULL
                  AND lower(po.project) = lower(p.project_name)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE purchase_orders AS po
                SET project_id = p.id
                FROM projects AS p
                WHERE po.project_id IS NULL
                  AND po.project IS NOT NULL
                  AND p.erpnext_id IS NOT NULL
                  AND lower(po.project) = lower(p.erpnext_id)
                """
            )
        )

    # JournalEntryItem.account_id ← accounts.account_name / account_number / erpnext_id
    if has_column("journal_entry_items", "account_id") and inspector.has_table("accounts"):
        op.execute(
            sa.text(
                """
                UPDATE journal_entry_items AS jei
                SET account_id = a.id
                FROM accounts AS a
                WHERE jei.account_id IS NULL
                  AND jei.account IS NOT NULL
                  AND lower(jei.account) = lower(a.account_name)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE journal_entry_items AS jei
                SET account_id = a.id
                FROM accounts AS a
                WHERE jei.account_id IS NULL
                  AND jei.account IS NOT NULL
                  AND a.account_number IS NOT NULL
                  AND lower(jei.account) = lower(a.account_number)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE journal_entry_items AS jei
                SET account_id = a.id
                FROM accounts AS a
                WHERE jei.account_id IS NULL
                  AND jei.account IS NOT NULL
                  AND a.erpnext_id IS NOT NULL
                  AND lower(jei.account) = lower(a.erpnext_id)
                """
            )
        )

    # JournalEntryAccounts.account_id ← accounts.account_name / account_number / erpnext_id
    if has_column("journal_entry_accounts", "account_id") and inspector.has_table("accounts"):
        op.execute(
            sa.text(
                """
                UPDATE journal_entry_accounts AS jea
                SET account_id = a.id
                FROM accounts AS a
                WHERE jea.account_id IS NULL
                  AND jea.account IS NOT NULL
                  AND lower(jea.account) = lower(a.account_name)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE journal_entry_accounts AS jea
                SET account_id = a.id
                FROM accounts AS a
                WHERE jea.account_id IS NULL
                  AND jea.account IS NOT NULL
                  AND a.account_number IS NOT NULL
                  AND lower(jea.account) = lower(a.account_number)
                """
            )
        )
        op.execute(
            sa.text(
                """
                UPDATE journal_entry_accounts AS jea
                SET account_id = a.id
                FROM accounts AS a
                WHERE jea.account_id IS NULL
                  AND jea.account IS NOT NULL
                  AND a.erpnext_id IS NOT NULL
                  AND lower(jea.account) = lower(a.erpnext_id)
                """
            )
        )


def downgrade() -> None:
    """No-op: backfill only populates FK columns."""
    pass
