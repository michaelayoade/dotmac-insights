"""Add expense management tables and seed defaults.

Revision ID: 20240920_add_expense_management
Revises: 20240915_add_tasks
Create Date: 2024-09-20
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20240920_add_expense_management"
down_revision: Union[str, None] = "20240915_add_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enumerations
    expense_claim_status = sa.Enum(
        "draft",
        "pending_approval",
        "approved",
        "rejected",
        "returned",
        "recalled",
        "posted",
        "paid",
        "reversed",
        "cancelled",
        name="expenseclaimstatus",
    )
    funding_method = sa.Enum(
        "out_of_pocket",
        "cash_advance",
        "corporate_card",
        "per_diem",
        name="fundingmethod",
    )
    cash_advance_status = sa.Enum(
        "draft",
        "pending_approval",
        "approved",
        "rejected",
        "disbursed",
        "partially_settled",
        "fully_settled",
        "cancelled",
        "written_off",
        name="cashadvancestatus",
    )
    line_status = sa.Enum(
        "pending",
        "approved",
        "rejected",
        "adjusted",
        name="linestatus",
    )
    corporate_card_status = sa.Enum(
        "active",
        "suspended",
        "cancelled",
        name="corporatecardstatus",
    )
    card_transaction_status = sa.Enum(
        "imported",
        "matched",
        "unmatched",
        "disputed",
        "excluded",
        "personal",
        name="cardtransactionstatus",
    )
    statement_status = sa.Enum(
        "open",
        "reconciled",
        "closed",
        name="statementstatus",
    )

    expense_claim_status.create(op.get_bind(), checkfirst=True)
    funding_method.create(op.get_bind(), checkfirst=True)
    cash_advance_status.create(op.get_bind(), checkfirst=True)
    line_status.create(op.get_bind(), checkfirst=True)
    corporate_card_status.create(op.get_bind(), checkfirst=True)
    card_transaction_status.create(op.get_bind(), checkfirst=True)
    statement_status.create(op.get_bind(), checkfirst=True)

    # Tables
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("is_group", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expense_account", sa.String(length=255), nullable=False),
        sa.Column("payable_account", sa.String(length=255), nullable=True),
        sa.Column("category_type", sa.String(length=50), nullable=True),
        sa.Column("default_tax_code_id", sa.Integer(), nullable=True),
        sa.Column("is_tax_deductible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requires_receipt", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.ForeignKeyConstraint(["parent_id"], ["expense_categories.id"]),
        sa.ForeignKeyConstraint(["default_tax_code_id"], ["tax_codes.id"]),
    )
    op.create_index("ix_expense_categories_id", "expense_categories", ["id"])
    op.create_index("ix_expense_categories_code", "expense_categories", ["code"])
    op.create_index("ix_expense_categories_parent_id", "expense_categories", ["parent_id"])
    op.create_index("ix_expense_categories_is_active", "expense_categories", ["is_active"])

    op.create_table(
        "expense_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("policy_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("applies_to_all", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("designation_id", sa.Integer(), nullable=True),
        sa.Column("employment_type", sa.String(length=100), nullable=True),
        sa.Column("grade_level", sa.String(length=50), nullable=True),
        sa.Column("max_single_expense", sa.Numeric(18, 4), nullable=True),
        sa.Column("max_daily_limit", sa.Numeric(18, 4), nullable=True),
        sa.Column("max_monthly_limit", sa.Numeric(18, 4), nullable=True),
        sa.Column("max_claim_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="NGN"),
        sa.Column("receipt_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("receipt_threshold", sa.Numeric(18, 4), nullable=True),
        sa.Column("auto_approve_below", sa.Numeric(18, 4), nullable=True),
        sa.Column("requires_pre_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_out_of_pocket", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_cash_advance", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_corporate_card", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_per_diem", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["category_id"], ["expense_categories.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["designation_id"], ["designations.id"]),
    )
    op.create_index("ix_expense_policies_id", "expense_policies", ["id"])
    op.create_index("ix_expense_policies_category_id", "expense_policies", ["category_id"])
    op.create_index("ix_expense_policies_is_active", "expense_policies", ["is_active"])

    op.create_table(
        "cash_advances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("advance_number", sa.String(length=100), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("trip_start_date", sa.Date(), nullable=True),
        sa.Column("trip_end_date", sa.Date(), nullable=True),
        sa.Column("destination", sa.String(length=255), nullable=True),
        sa.Column("requested_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("approved_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("disbursed_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("settled_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("outstanding_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("refund_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="NGN"),
        sa.Column("base_currency", sa.String(length=10), nullable=False, server_default="NGN"),
        sa.Column("conversion_rate", sa.Numeric(18, 10), nullable=False, server_default="1"),
        sa.Column("base_requested_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("status", cash_advance_status, nullable=False, server_default="draft"),
        sa.Column("docstatus", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("required_by_date", sa.Date(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("disbursed_at", sa.DateTime(), nullable=True),
        sa.Column("settlement_due_date", sa.Date(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("mode_of_payment", sa.String(length=100), nullable=True),
        sa.Column("bank_account_id", sa.Integer(), nullable=True),
        sa.Column("payment_reference", sa.String(length=255), nullable=True),
        sa.Column("disbursed_by_id", sa.Integer(), nullable=True),
        sa.Column("journal_entry_id", sa.Integer(), nullable=True),
        sa.Column("advance_account", sa.String(length=255), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"]),
        sa.UniqueConstraint("advance_number"),
    )
    op.create_index("ix_cash_advances_id", "cash_advances", ["id"])
    op.create_index("ix_cash_advances_employee", "cash_advances", ["employee_id"])
    op.create_index("ix_cash_advances_status", "cash_advances", ["status"])
    op.create_index("ix_cash_advances_request_date", "cash_advances", ["request_date"])

    op.create_table(
        "expense_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_number", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("cost_center", sa.String(length=255), nullable=True),
        sa.Column("claim_date", sa.Date(), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=True),
        sa.Column("expense_period_start", sa.Date(), nullable=True),
        sa.Column("expense_period_end", sa.Date(), nullable=True),
        sa.Column("total_claimed_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_sanctioned_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_advance_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_reimbursable", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_taxes", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="NGN"),
        sa.Column("base_currency", sa.String(length=10), nullable=False, server_default="NGN"),
        sa.Column("conversion_rate", sa.Numeric(18, 10), nullable=False, server_default="1"),
        sa.Column("base_total_claimed", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("base_total_sanctioned", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("out_of_pocket_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("corporate_card_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("cash_advance_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("per_diem_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("cash_advance_id", sa.Integer(), nullable=True),
        sa.Column("status", expense_claim_status, nullable=False, server_default="draft"),
        sa.Column("docstatus", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("workflow_status", sa.String(length=100), nullable=True),
        sa.Column("approval_status", sa.String(length=50), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("return_reason", sa.Text(), nullable=True),
        sa.Column("payment_status", sa.String(length=50), nullable=True),
        sa.Column("amount_paid", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("payment_date", sa.DateTime(), nullable=True),
        sa.Column("payment_reference", sa.String(length=255), nullable=True),
        sa.Column("journal_entry_id", sa.Integer(), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("posted_by_id", sa.Integer(), nullable=True),
        sa.Column("fiscal_period_id", sa.Integer(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(), nullable=True),
        sa.Column("reversed_by_id", sa.Integer(), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("reversal_journal_entry_id", sa.Integer(), nullable=True),
        sa.Column("payable_account", sa.String(length=255), nullable=True),
        sa.Column("mode_of_payment", sa.String(length=100), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_number"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["cash_advance_id"], ["cash_advances.id"]),
    )
    op.create_index("ix_expense_claims_id", "expense_claims", ["id"])
    op.create_index("ix_expense_claims_employee_date", "expense_claims", ["employee_id", "claim_date"])
    op.create_index("ix_expense_claims_status_date", "expense_claims", ["status", "claim_date"])

    op.create_table(
        "per_diem_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rate_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("location_tier", sa.String(length=50), nullable=True),
        sa.Column("full_day_rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("half_day_rate", sa.Numeric(18, 4), nullable=True),
        sa.Column("overnight_rate", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="NGN"),
        sa.Column("meals_allowance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("lodging_allowance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("incidentals_allowance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("designation_id", sa.Integer(), nullable=True),
        sa.Column("grade_level", sa.String(length=50), nullable=True),
        sa.Column("expense_account", sa.String(length=255), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["designation_id"], ["designations.id"]),
    )
    op.create_index("ix_per_diem_rates_id", "per_diem_rates", ["id"])
    op.create_index("ix_per_diem_rates_location", "per_diem_rates", ["country", "city"])
    op.create_index("ix_per_diem_rates_is_active", "per_diem_rates", ["is_active"])

    op.create_table(
        "mileage_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rate_name", sa.String(length=255), nullable=False),
        sa.Column("vehicle_type", sa.String(length=50), nullable=False),
        sa.Column("rate_per_km", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="NGN"),
        sa.Column("first_tier_km", sa.Numeric(18, 2), nullable=True),
        sa.Column("first_tier_rate", sa.Numeric(18, 4), nullable=True),
        sa.Column("expense_account", sa.String(length=255), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mileage_rates_id", "mileage_rates", ["id"])
    op.create_index("ix_mileage_rates_is_active", "mileage_rates", ["is_active"])

    op.create_table(
        "corporate_cards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_number_last4", sa.String(length=4), nullable=False),
        sa.Column("card_name", sa.String(length=255), nullable=False),
        sa.Column("card_type", sa.String(length=50), nullable=True),
        sa.Column("bank_name", sa.String(length=255), nullable=True),
        sa.Column("card_provider", sa.String(length=100), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("credit_limit", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("single_transaction_limit", sa.Numeric(18, 4), nullable=True),
        sa.Column("daily_limit", sa.Numeric(18, 4), nullable=True),
        sa.Column("monthly_limit", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="NGN"),
        sa.Column("status", corporate_card_status, nullable=False, server_default="active"),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("liability_account", sa.String(length=255), nullable=True),
        sa.Column("bank_account_id", sa.Integer(), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"]),
    )
    op.create_index("ix_corporate_cards_id", "corporate_cards", ["id"])
    op.create_index("ix_corporate_cards_employee_id", "corporate_cards", ["employee_id"])
    op.create_index("ix_corporate_cards_status", "corporate_cards", ["status"])

    op.create_table(
        "expense_claim_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("expense_claim_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("merchant_name", sa.String(length=255), nullable=True),
        sa.Column("merchant_tax_id", sa.String(length=100), nullable=True),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column("claimed_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("sanctioned_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="NGN"),
        sa.Column("tax_code_id", sa.Integer(), nullable=True),
        sa.Column("tax_rate", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("is_tax_inclusive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_tax_reclaimable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("withholding_tax_rate", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("withholding_tax_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("conversion_rate", sa.Numeric(18, 10), nullable=False, server_default="1"),
        sa.Column("base_claimed_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("base_sanctioned_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("rate_source", sa.String(length=50), nullable=True),
        sa.Column("rate_date", sa.Date(), nullable=True),
        sa.Column("funding_method", funding_method, nullable=False, server_default="out_of_pocket"),
        sa.Column("corporate_card_transaction_id", sa.Integer(), nullable=True),
        sa.Column("expense_account", sa.String(length=255), nullable=True),
        sa.Column("cost_center", sa.String(length=255), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("has_receipt", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("receipt_missing_reason", sa.String(length=255), nullable=True),
        sa.Column("distance_km", sa.Numeric(18, 2), nullable=True),
        sa.Column("mileage_rate", sa.Numeric(18, 4), nullable=True),
        sa.Column("is_per_diem", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("per_diem_rate_id", sa.Integer(), nullable=True),
        sa.Column("per_diem_days", sa.Numeric(18, 2), nullable=True),
        sa.Column("line_status", line_status, nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("adjustment_reason", sa.String(length=500), nullable=True),
        sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["expense_claim_id"], ["expense_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["expense_categories.id"]),
        sa.ForeignKeyConstraint(["tax_code_id"], ["tax_codes.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["per_diem_rate_id"], ["per_diem_rates.id"]),
    )
    op.create_index("ix_expense_claim_lines_id", "expense_claim_lines", ["id"])
    op.create_index("ix_expense_claim_lines_date", "expense_claim_lines", ["expense_date"])

    op.create_table(
        "corporate_card_statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("statement_date", sa.Date(), nullable=True),
        sa.Column("import_date", sa.DateTime(), nullable=False),
        sa.Column("import_source", sa.String(length=100), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("status", statement_status, nullable=False, server_default="open"),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unmatched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reconciled_at", sa.DateTime(), nullable=True),
        sa.Column("reconciled_by_id", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["card_id"], ["corporate_cards.id"]),
    )
    op.create_index(
        "ix_corp_card_statements_card_period",
        "corporate_card_statements",
        ["card_id", "period_start", "period_end"],
    )

    op.create_table(
        "corporate_card_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=True),
        sa.Column("transaction_date", sa.DateTime(), nullable=False),
        sa.Column("posting_date", sa.DateTime(), nullable=True),
        sa.Column("merchant_name", sa.String(length=255), nullable=True),
        sa.Column("merchant_category_code", sa.String(length=10), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="NGN"),
        sa.Column("original_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("original_currency", sa.String(length=10), nullable=True),
        sa.Column("conversion_rate", sa.Numeric(18, 10), nullable=False, server_default="1"),
        sa.Column("transaction_reference", sa.String(length=255), nullable=True),
        sa.Column("authorization_code", sa.String(length=50), nullable=True),
        sa.Column("status", card_transaction_status, nullable=False, server_default="imported"),
        sa.Column("expense_claim_line_id", sa.Integer(), nullable=True),
        sa.Column("match_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("disputed_at", sa.DateTime(), nullable=True),
        sa.Column("dispute_reason", sa.Text(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("import_hash", sa.String(length=64), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["card_id"], ["corporate_cards.id"]),
        sa.ForeignKeyConstraint(["statement_id"], ["corporate_card_statements.id"]),
        sa.ForeignKeyConstraint(["expense_claim_line_id"], ["expense_claim_lines.id"]),
    )
    op.create_index("ix_corporate_card_transactions_id", "corporate_card_transactions", ["id"])
    op.create_index("ix_corporate_card_transactions_card", "corporate_card_transactions", ["card_id"])
    op.create_index("ix_corporate_card_transactions_status", "corporate_card_transactions", ["status"])
    op.create_index("ix_corporate_card_transactions_import_hash", "corporate_card_transactions", ["import_hash"])

    # Seed default categories
    categories = [
        {"code": "TRAVEL", "name": "Travel", "expense_account": "Expense - Travel"},
        {"code": "MEALS", "name": "Meals & Entertainment", "expense_account": "Expense - Meals"},
        {"code": "TRANSPORT", "name": "Transport", "expense_account": "Expense - Transport"},
        {"code": "SUPPLIES", "name": "Office Supplies", "expense_account": "Expense - Supplies"},
        {"code": "OTHER", "name": "Other", "expense_account": "Expense - Misc"},
    ]
    op.bulk_insert(
        sa.table(
            "expense_categories",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("expense_account", sa.String),
            sa.column("is_system", sa.Boolean),
        ),
        [{**c, "is_system": True} for c in categories],
    )

    # Seed default policy (out-of-pocket only)
    policy_table = sa.table(
        "expense_policies",
        sa.column("policy_name", sa.String),
        sa.column("applies_to_all", sa.Boolean),
        sa.column("allow_out_of_pocket", sa.Boolean),
        sa.column("allow_cash_advance", sa.Boolean),
        sa.column("allow_corporate_card", sa.Boolean),
        sa.column("allow_per_diem", sa.Boolean),
        sa.column("currency", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("priority", sa.Integer),
    )
    op.bulk_insert(
        policy_table,
        [
            {
                "policy_name": "Default Expense Policy",
                "applies_to_all": True,
                "allow_out_of_pocket": True,
                "allow_cash_advance": False,
                "allow_corporate_card": False,
                "allow_per_diem": False,
                "currency": "NGN",
                "is_active": True,
                "priority": 0,
            }
        ],
    )

    # Seed document number formats for expense claim and cash advance if table exists
    try:
        op.bulk_insert(
            sa.table(
                "document_number_formats",
                sa.column("document_type", sa.String),
                sa.column("company", sa.String),
                sa.column("prefix", sa.String),
                sa.column("format_pattern", sa.String),
                sa.column("min_digits", sa.Integer),
                sa.column("starting_number", sa.Integer),
                sa.column("current_number", sa.Integer),
                sa.column("reset_frequency", sa.String),
                sa.column("is_active", sa.Boolean),
            ),
            [
                {
                    "document_type": "expense_claim",
                    "company": None,
                    "prefix": "EXP",
                    "format_pattern": "{PREFIX}-{YYYY}-{####}",
                    "min_digits": 4,
                    "starting_number": 1,
                    "current_number": 0,
                    "reset_frequency": "yearly",
                    "is_active": True,
                },
                {
                    "document_type": "cash_advance",
                    "company": None,
                    "prefix": "ADV",
                    "format_pattern": "{PREFIX}-{YYYY}-{####}",
                    "min_digits": 4,
                    "starting_number": 1,
                    "current_number": 0,
                    "reset_frequency": "yearly",
                    "is_active": True,
                },
            ],
        )
    except Exception:
        # Table may not exist in some environments; ignore seed failure.
        pass

    # Seed default approval workflows (single-step) for expense claims and cash advances
    try:
        # Insert workflows
        op.bulk_insert(
            sa.table(
                "approval_workflows",
                sa.column("workflow_name", sa.String),
                sa.column("description", sa.Text),
                sa.column("doctype", sa.String),
                sa.column("is_active", sa.Boolean),
                sa.column("is_mandatory", sa.Boolean),
            ),
            [
                {
                    "workflow_name": "Expense Claim Default",
                    "description": "Single-step approval for expense claims",
                    "doctype": "expense_claim",
                    "is_active": True,
                    "is_mandatory": True,
                },
                {
                    "workflow_name": "Cash Advance Default",
                    "description": "Single-step approval for cash advances",
                    "doctype": "cash_advance",
                    "is_active": True,
                    "is_mandatory": True,
                },
            ],
        )

        # Fetch inserted workflow ids
        conn = op.get_bind()
        wf_rows = conn.execute(sa.text("select id, doctype from approval_workflows where workflow_name in ('Expense Claim Default','Cash Advance Default')")).fetchall()
        wf_map = {row.doctype: row.id for row in wf_rows}

        # Insert steps
        steps = []
        if "expense_claim" in wf_map:
            steps.append(
                {
                    "workflow_id": wf_map["expense_claim"],
                    "step_order": 1,
                    "step_name": "Manager Approval",
                    "role_required": "expense_approver",
                    "approval_mode": "any",
                }
            )
        if "cash_advance" in wf_map:
            steps.append(
                {
                    "workflow_id": wf_map["cash_advance"],
                    "step_order": 1,
                    "step_name": "Manager Approval",
                    "role_required": "expense_approver",
                    "approval_mode": "any",
                }
            )
        if steps:
            op.bulk_insert(
                sa.table(
                    "approval_steps",
                    sa.column("workflow_id", sa.Integer),
                    sa.column("step_order", sa.Integer),
                    sa.column("step_name", sa.String),
                    sa.column("role_required", sa.String),
                    sa.column("approval_mode", sa.String),
                ),
                steps,
            )
    except Exception:
        # Approval tables may not exist in some environments; skip seed if so.
        pass


def downgrade() -> None:
    op.drop_table("corporate_card_transactions")
    op.drop_index("ix_corp_card_statements_card_period", table_name="corporate_card_statements")
    op.drop_table("corporate_card_statements")
    op.drop_table("expense_claim_lines")
    op.drop_table("corporate_cards")
    op.drop_table("mileage_rates")
    op.drop_table("per_diem_rates")
    op.drop_index("ix_expense_claims_status_date", table_name="expense_claims")
    op.drop_index("ix_expense_claims_employee_date", table_name="expense_claims")
    op.drop_index("ix_expense_claims_id", table_name="expense_claims")
    op.drop_table("expense_claims")
    op.drop_index("ix_cash_advances_request_date", table_name="cash_advances")
    op.drop_index("ix_cash_advances_status", table_name="cash_advances")
    op.drop_index("ix_cash_advances_employee", table_name="cash_advances")
    op.drop_index("ix_cash_advances_id", table_name="cash_advances")
    op.drop_table("cash_advances")
    op.drop_index("ix_expense_policies_is_active", table_name="expense_policies")
    op.drop_index("ix_expense_policies_category_id", table_name="expense_policies")
    op.drop_index("ix_expense_policies_id", table_name="expense_policies")
    op.drop_table("expense_policies")
    op.drop_index("ix_expense_categories_is_active", table_name="expense_categories")
    op.drop_index("ix_expense_categories_parent_id", table_name="expense_categories")
    op.drop_index("ix_expense_categories_code", table_name="expense_categories")
    op.drop_index("ix_expense_categories_id", table_name="expense_categories")
    op.drop_table("expense_categories")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS statementstatus")
    op.execute("DROP TYPE IF EXISTS cardtransactionstatus")
    op.execute("DROP TYPE IF EXISTS corporatecardstatus")
    op.execute("DROP TYPE IF EXISTS linestatus")
    op.execute("DROP TYPE IF EXISTS cashadvancestatus")
    op.execute("DROP TYPE IF EXISTS fundingmethod")
    op.execute("DROP TYPE IF EXISTS expenseclaimstatus")
