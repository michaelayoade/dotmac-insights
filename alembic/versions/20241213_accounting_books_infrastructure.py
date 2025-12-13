"""accounting_books_infrastructure

Revision ID: 20241213_accounting_books_infrastructure
Revises: 5bde4be2482f
Create Date: 2024-12-13

Adds infrastructure tables for accounting books module:
- fiscal_periods: Period-based closing control
- approval_workflows, approval_steps: Workflow configuration
- document_approvals, approval_history: Document approval tracking
- audit_logs: Immutable audit trail
- exchange_rates, revaluation_entries: Multi-currency support
- accounting_controls: Global/per-company settings
- voucher_sequences: Auto-numbering support
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241213_accounting_books_infrastructure"
down_revision: Union[str, None] = "5bde4be2482f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # FISCAL PERIODS
    # ==========================================================================
    op.create_table(
        "fiscal_periods",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("fiscal_year_id", sa.Integer(), sa.ForeignKey("fiscal_years.id"), nullable=False, index=True),
        sa.Column("period_name", sa.String(50), nullable=False),
        sa.Column("period_type", sa.String(20), nullable=False),  # month, quarter, year
        sa.Column("start_date", sa.Date(), nullable=False, index=True),
        sa.Column("end_date", sa.Date(), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open", index=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reopened_at", sa.DateTime(), nullable=True),
        sa.Column("reopened_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closing_journal_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_fiscal_period_name", "fiscal_periods", ["fiscal_year_id", "period_name"])
    op.create_index("ix_fiscal_periods_dates", "fiscal_periods", ["start_date", "end_date"])

    # ==========================================================================
    # APPROVAL WORKFLOWS
    # ==========================================================================
    op.create_table(
        "approval_workflows",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("workflow_name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("doctype", sa.String(100), nullable=False, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true(), index=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("escalation_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("escalation_hours", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # ==========================================================================
    # APPROVAL STEPS
    # ==========================================================================
    op.create_table(
        "approval_steps",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(255), nullable=False),
        sa.Column("role_required", sa.String(100), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approval_mode", sa.String(20), nullable=False, server_default="any"),  # any, all, sequential
        sa.Column("amount_threshold_min", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("amount_threshold_max", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("auto_approve_below", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("escalation_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("escalation_role", sa.String(100), nullable=True),
        sa.Column("can_reject", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
    )
    op.create_unique_constraint("uq_workflow_step_order", "approval_steps", ["workflow_id", "step_order"])

    # ==========================================================================
    # DOCUMENT APPROVALS
    # ==========================================================================
    op.create_table(
        "document_approvals",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("doctype", sa.String(100), nullable=False, index=True),
        sa.Column("document_id", sa.Integer(), nullable=False, index=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("approval_workflows.id"), nullable=False, index=True),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft", index=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("step_approved_at", sa.DateTime(), nullable=True),
        sa.Column("step_approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("step_remarks", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("posted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("escalated_at", sa.DateTime(), nullable=True),
        sa.Column("escalation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_document_approval", "document_approvals", ["doctype", "document_id"])
    op.create_index("ix_document_approvals_status_doctype", "document_approvals", ["status", "doctype"])

    # ==========================================================================
    # APPROVAL HISTORY
    # ==========================================================================
    op.create_table(
        "approval_history",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("document_approval_id", sa.Integer(), sa.ForeignKey("document_approvals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("action_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )

    # ==========================================================================
    # AUDIT LOGS (Immutable)
    # ==========================================================================
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("doctype", sa.String(100), nullable=False, index=True),
        sa.Column("document_id", sa.Integer(), nullable=False, index=True),
        sa.Column("document_name", sa.String(255), nullable=True),
        sa.Column("action", sa.String(50), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), nullable=True, index=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("user_name", sa.String(255), nullable=True),
        sa.Column("old_values", postgresql.JSONB(), nullable=True),
        sa.Column("new_values", postgresql.JSONB(), nullable=True),
        sa.Column("changed_fields", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_audit_logs_doctype_docid", "audit_logs", ["doctype", "document_id"])
    op.create_index("ix_audit_logs_timestamp_action", "audit_logs", ["timestamp", "action"])

    # ==========================================================================
    # EXCHANGE RATES
    # ==========================================================================
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("from_currency", sa.String(3), nullable=False, index=True),
        sa.Column("to_currency", sa.String(3), nullable=False, index=True),
        sa.Column("rate_date", sa.Date(), nullable=False, index=True),
        sa.Column("rate", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_unique_constraint("uq_exchange_rate", "exchange_rates", ["from_currency", "to_currency", "rate_date"])
    op.create_index("ix_exchange_rates_pair_date", "exchange_rates", ["from_currency", "to_currency", "rate_date"])

    # ==========================================================================
    # REVALUATION ENTRIES
    # ==========================================================================
    op.create_table(
        "revaluation_entries",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("fiscal_period_id", sa.Integer(), sa.ForeignKey("fiscal_periods.id"), nullable=False, index=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False, index=True),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("original_currency", sa.String(3), nullable=False),
        sa.Column("original_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("exchange_rate_used", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("revalued_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("gain_loss_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("is_realized", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("journal_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_revaluation_period_account", "revaluation_entries", ["fiscal_period_id", "account_id"])

    # ==========================================================================
    # ACCOUNTING CONTROLS
    # ==========================================================================
    op.create_table(
        "accounting_controls",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("company", sa.String(255), nullable=True, unique=True),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("backdating_days_allowed", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("future_posting_days_allowed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_voucher_numbering", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("voucher_prefix_format", sa.String(100), nullable=True),
        sa.Column("require_attachment_journal_entry", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("require_attachment_expense", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("require_attachment_payment", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("require_attachment_invoice", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("require_approval_journal_entry", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("require_approval_expense", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("require_approval_payment", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("auto_create_fiscal_periods", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("default_period_type", sa.String(20), nullable=False, server_default="month"),
        sa.Column("retained_earnings_account", sa.String(255), nullable=True),
        sa.Column("fx_gain_account", sa.String(255), nullable=True),
        sa.Column("fx_loss_account", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # ==========================================================================
    # VOUCHER SEQUENCES
    # ==========================================================================
    op.create_table(
        "voucher_sequences",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("prefix", sa.String(50), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("current_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_voucher_sequence", "voucher_sequences", ["prefix", "company"])

    # ==========================================================================
    # INSERT DEFAULT ACCOUNTING CONTROL (Global)
    # ==========================================================================
    op.execute("""
        INSERT INTO accounting_controls (company, base_currency, backdating_days_allowed, future_posting_days_allowed)
        VALUES (NULL, 'NGN', 7, 0)
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("voucher_sequences")
    op.drop_table("accounting_controls")
    op.drop_table("revaluation_entries")
    op.drop_table("exchange_rates")
    op.drop_table("audit_logs")
    op.drop_table("approval_history")
    op.drop_table("document_approvals")
    op.drop_table("approval_steps")
    op.drop_table("approval_workflows")
    op.drop_table("fiscal_periods")
