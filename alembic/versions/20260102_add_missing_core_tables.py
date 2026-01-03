"""Add missing core tables for tax config, radius, templates, and transactions.

Revision ID: 20260102_add_missing_core_tables
Revises: add_employee_party_id
Create Date: 2026-01-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260102_add_missing_core_tables"
down_revision = "add_employee_party_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------------
    # Enum types
    # ---------------------------------------------------------------------
    tax_category_type_enum_create = postgresql.ENUM(
        "sales_tax",
        "withholding",
        "income_tax",
        "excise",
        "customs",
        "stamp_duty",
        "other",
        name="taxcategorytype",
    )
    tax_category_type_enum = postgresql.ENUM(
        "sales_tax",
        "withholding",
        "income_tax",
        "excise",
        "customs",
        "stamp_duty",
        "other",
        name="taxcategorytype",
        create_type=False,
    )
    tax_transaction_type_enum_create = postgresql.ENUM(
        "output",
        "input",
        "withholding",
        "remittance",
        name="taxtransactiontype",
    )
    tax_transaction_type_enum = postgresql.ENUM(
        "output",
        "input",
        "withholding",
        "remittance",
        name="taxtransactiontype",
        create_type=False,
    )
    tax_transaction_status_enum_create = postgresql.ENUM(
        "draft",
        "confirmed",
        "filed",
        "paid",
        "void",
        name="taxtransactionstatus",
    )
    tax_transaction_status_enum = postgresql.ENUM(
        "draft",
        "confirmed",
        "filed",
        "paid",
        "void",
        name="taxtransactionstatus",
        create_type=False,
    )
    # Tax filing frequency already exists via tax_regions.
    tax_filing_frequency_enum = postgresql.ENUM(
        "monthly",
        "quarterly",
        "semi_annual",
        "annual",
        name="taxfilingfrequency",
        create_type=False,
    )

    auth_type_enum_create = postgresql.ENUM(
        "PAP",
        "CHAP",
        "MSCHAP",
        "MSCHAPV2",
        "EAP",
        name="authenticationtype",
    )
    auth_type_enum = postgresql.ENUM(
        "PAP",
        "CHAP",
        "MSCHAP",
        "MSCHAPV2",
        "EAP",
        name="authenticationtype",
        create_type=False,
    )
    password_encryption_enum_create = postgresql.ENUM(
        "CLEARTEXT",
        "NT_HASH",
        "SSHA",
        "CRYPT",
        name="passwordencryption",
    )
    password_encryption_enum = postgresql.ENUM(
        "CLEARTEXT",
        "NT_HASH",
        "SSHA",
        "CRYPT",
        name="passwordencryption",
        create_type=False,
    )
    accounting_method_enum_create = postgresql.ENUM(
        "RADIUS",
        "RADIUS_PLUS_COA",
        "API_ONLY",
        name="accountingmethod",
    )
    accounting_method_enum = postgresql.ENUM(
        "RADIUS",
        "RADIUS_PLUS_COA",
        "API_ONLY",
        name="accountingmethod",
        create_type=False,
    )
    session_limit_action_enum_create = postgresql.ENUM(
        "REJECT",
        "DISCONNECT_OLDEST",
        "ALLOW",
        name="sessionlimitaction",
    )
    session_limit_action_enum = postgresql.ENUM(
        "REJECT",
        "DISCONNECT_OLDEST",
        "ALLOW",
        name="sessionlimitaction",
        create_type=False,
    )
    bandwidth_unit_enum_create = postgresql.ENUM(
        "KBPS",
        "MBPS",
        "GBPS",
        name="bandwidthunit",
    )
    bandwidth_unit_enum = postgresql.ENUM(
        "KBPS",
        "MBPS",
        "GBPS",
        name="bandwidthunit",
        create_type=False,
    )
    nastype_enum_create = postgresql.ENUM(
        "MIKROTIK",
        "CISCO",
        "UBIQUITI",
        "HUAWEI",
        "JUNIPER",
        "OTHER",
        name="nastype",
    )
    nastype_enum = postgresql.ENUM(
        "MIKROTIK",
        "CISCO",
        "UBIQUITI",
        "HUAWEI",
        "JUNIPER",
        "OTHER",
        name="nastype",
        create_type=False,
    )
    nastype_enum_no_create = postgresql.ENUM(
        "MIKROTIK",
        "CISCO",
        "UBIQUITI",
        "HUAWEI",
        "JUNIPER",
        "OTHER",
        name="nastype",
        create_type=False,
    )
    project_priority_enum = postgresql.ENUM(
        "low",
        "medium",
        "high",
        name="projectpriority",
        create_type=False,
    )

    bind = op.get_bind()
    tax_category_type_enum_create.create(bind, checkfirst=True)
    tax_transaction_type_enum_create.create(bind, checkfirst=True)
    tax_transaction_status_enum_create.create(bind, checkfirst=True)
    auth_type_enum_create.create(bind, checkfirst=True)
    password_encryption_enum_create.create(bind, checkfirst=True)
    accounting_method_enum_create.create(bind, checkfirst=True)
    session_limit_action_enum_create.create(bind, checkfirst=True)
    bandwidth_unit_enum_create.create(bind, checkfirst=True)
    nastype_enum_create.create(bind, checkfirst=True)

    # ---------------------------------------------------------------------
    # Generic tax config tables
    # ---------------------------------------------------------------------
    op.create_table(
        "generic_tax_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("tax_regions.id"), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_type", tax_category_type_enum, nullable=False),
        sa.Column("default_rate", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("is_recoverable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_inclusive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("applies_to_purchases", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("applies_to_sales", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("filing_frequency", tax_filing_frequency_enum, nullable=True),
        sa.Column("filing_deadline_day", sa.Integer(), nullable=True),
        sa.Column("output_account", sa.String(length=255), nullable=True),
        sa.Column("input_account", sa.String(length=255), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("region_id", "code", name="uq_generic_tax_categories_region_code"),
    )
    op.create_index(
        "ix_generic_tax_categories_region",
        "generic_tax_categories",
        ["region_id"],
    )
    op.create_index(
        "ix_generic_tax_categories_code",
        "generic_tax_categories",
        ["code"],
    )
    op.create_index(
        "ix_generic_tax_categories_category_type",
        "generic_tax_categories",
        ["category_type"],
    )

    op.create_table(
        "tax_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("generic_tax_categories.id"), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("rate", sa.Numeric(10, 6), nullable=False),
        sa.Column("conditions", postgresql.JSONB(), nullable=True),
        sa.Column("min_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("max_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tax_rates_category_id", "tax_rates", ["category_id"])
    op.create_index(
        "ix_tax_rates_category_effective",
        "tax_rates",
        ["category_id", "effective_from", "effective_to"],
    )

    op.create_table(
        "tax_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("tax_regions.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("generic_tax_categories.id"), nullable=False),
        sa.Column("reference_number", sa.String(length=100), nullable=False),
        sa.Column("transaction_type", tax_transaction_type_enum, nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("party_type", sa.String(length=50), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=True),
        sa.Column("party_name", sa.String(length=255), nullable=False),
        sa.Column("party_tax_id", sa.String(length=50), nullable=True),
        sa.Column("taxable_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(10, 6), nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("exchange_rate", sa.Numeric(12, 6), nullable=False, server_default="1"),
        sa.Column("base_tax_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("filing_period", sa.String(length=10), nullable=False),
        sa.Column("status", tax_transaction_status_enum, nullable=False, server_default="draft"),
        sa.Column("is_exempt", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_zero_rated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("exemption_reason", sa.String(length=255), nullable=True),
        sa.Column("source_doctype", sa.String(length=50), nullable=False),
        sa.Column("source_docname", sa.String(length=255), nullable=False),
        sa.Column("filed_at", sa.DateTime(), nullable=True),
        sa.Column("filed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("filing_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("reference_number", name="uq_tax_transactions_reference_number"),
    )
    op.create_index("ix_tax_transactions_region_id", "tax_transactions", ["region_id"])
    op.create_index("ix_tax_transactions_category_id", "tax_transactions", ["category_id"])
    op.create_index("ix_tax_transactions_reference_number", "tax_transactions", ["reference_number"])
    op.create_index("ix_tax_transactions_transaction_type", "tax_transactions", ["transaction_type"])
    op.create_index("ix_tax_transactions_transaction_date", "tax_transactions", ["transaction_date"])
    op.create_index("ix_tax_transactions_company", "tax_transactions", ["company"])
    op.create_index("ix_tax_transactions_filing_period", "tax_transactions", ["filing_period"])
    op.create_index("ix_tax_transactions_status", "tax_transactions", ["status"])
    op.create_index(
        "ix_tax_transactions_period",
        "tax_transactions",
        ["region_id", "filing_period"],
    )
    op.create_index(
        "ix_tax_transactions_company_period",
        "tax_transactions",
        ["company", "filing_period"],
    )
    op.create_index(
        "ix_tax_transactions_source",
        "tax_transactions",
        ["source_doctype", "source_docname"],
    )

    # ---------------------------------------------------------------------
    # RADIUS configuration tables
    # ---------------------------------------------------------------------
    op.create_table(
        "radius_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(length=255), nullable=True, unique=True),
        sa.Column("radius_host", sa.String(length=255), nullable=False, server_default="localhost"),
        sa.Column("radius_auth_port", sa.Integer(), nullable=False, server_default="1812"),
        sa.Column("radius_acct_port", sa.Integer(), nullable=False, server_default="1813"),
        sa.Column("radius_secret", sa.String(length=255), nullable=True),
        sa.Column("radius_secondary_host", sa.String(length=255), nullable=True),
        sa.Column("radius_secondary_auth_port", sa.Integer(), nullable=True, server_default="1812"),
        sa.Column("radius_secondary_acct_port", sa.Integer(), nullable=True, server_default="1813"),
        sa.Column("radius_secondary_secret", sa.String(length=255), nullable=True),
        sa.Column("failover_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("radius_timeout_seconds", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("radius_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("radius_dead_time_seconds", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("default_auth_type", auth_type_enum, nullable=False, server_default="PAP"),
        sa.Column("password_encryption", password_encryption_enum, nullable=False, server_default="CLEARTEXT"),
        sa.Column("mac_auth_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mac_auth_password", sa.String(length=255), nullable=True),
        sa.Column("mac_format", sa.String(length=50), nullable=False, server_default="XX:XX:XX:XX:XX:XX"),
        sa.Column("default_realm", sa.String(length=100), nullable=True),
        sa.Column("strip_realm", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("accounting_method", accounting_method_enum, nullable=False, server_default="RADIUS"),
        sa.Column("interim_update_interval_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("acct_delay_time_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("track_sessions", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("session_timeout_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idle_timeout_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("track_usage", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("aggregate_usage_daily", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_sessions_per_user", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("session_limit_action", session_limit_action_enum, nullable=False, server_default="REJECT"),
        sa.Column("simultaneous_use_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("coa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("coa_port", sa.Integer(), nullable=False, server_default="3799"),
        sa.Column("coa_secret", sa.String(length=255), nullable=True),
        sa.Column("coa_timeout_seconds", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("coa_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("bandwidth_unit", bandwidth_unit_enum, nullable=False, server_default="MBPS"),
        sa.Column("use_mikrotik_rate_limit", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("use_wispr_bandwidth", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("burst_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("burst_threshold_percent", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("burst_time_seconds", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("ip_pool_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("default_ip_pool", sa.String(length=100), nullable=True),
        sa.Column("ipv6_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("default_ipv6_pool", sa.String(length=100), nullable=True),
        sa.Column(
            "static_ip_reply_attribute",
            sa.String(length=100),
            nullable=False,
            server_default="Framed-IP-Address",
        ),
        sa.Column(
            "static_ipv6_reply_attribute",
            sa.String(length=100),
            nullable=False,
            server_default="Framed-IPv6-Address",
        ),
        sa.Column("default_nas_type", nastype_enum, nullable=False, server_default="MIKROTIK"),
        sa.Column("auto_add_nas", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("default_nas_secret", sa.String(length=255), nullable=True),
        sa.Column("nas_require_secret", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("radius_db_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("radius_db_host", sa.String(length=255), nullable=True),
        sa.Column("radius_db_port", sa.Integer(), nullable=True, server_default="3306"),
        sa.Column("radius_db_name", sa.String(length=100), nullable=True, server_default="radius"),
        sa.Column("radius_db_user", sa.String(length=100), nullable=True),
        sa.Column("radius_db_password", sa.String(length=255), nullable=True),
        sa.Column("radcheck_table", sa.String(length=100), nullable=False, server_default="radcheck"),
        sa.Column("radreply_table", sa.String(length=100), nullable=False, server_default="radreply"),
        sa.Column("radgroupcheck_table", sa.String(length=100), nullable=False, server_default="radgroupcheck"),
        sa.Column("radgroupreply_table", sa.String(length=100), nullable=False, server_default="radgroupreply"),
        sa.Column("radacct_table", sa.String(length=100), nullable=False, server_default="radacct"),
        sa.Column("nas_table", sa.String(length=100), nullable=False, server_default="nas"),
        sa.Column("log_auth_requests", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("log_acct_requests", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("log_failed_auth", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("debug_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("log_retention_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_radius_settings_company", "radius_settings", ["company"])

    op.create_table(
        "radius_attribute_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("nas_type", nastype_enum_no_create, nullable=False),
        sa.Column("attribute_name", sa.String(length=100), nullable=False),
        sa.Column("radius_attribute", sa.String(length=100), nullable=False),
        sa.Column("radius_vendor_id", sa.Integer(), nullable=True),
        sa.Column("radius_vendor_type", sa.Integer(), nullable=True),
        sa.Column("value_format", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("company", "nas_type", "attribute_name", name="uq_radius_attr_mapping"),
    )
    op.create_index(
        "ix_radius_attribute_mappings_company",
        "radius_attribute_mappings",
        ["company"],
    )

    op.create_table(
        "nas_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("routers.id"), nullable=False),
        sa.Column("nas_identifier", sa.String(length=255), nullable=True),
        sa.Column("radius_secret", sa.String(length=255), nullable=True),
        sa.Column("nas_type", nastype_enum_no_create, nullable=False, server_default="MIKROTIK"),
        sa.Column("coa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("coa_port", sa.Integer(), nullable=False, server_default="3799"),
        sa.Column("coa_secret", sa.String(length=255), nullable=True),
        sa.Column("interim_interval", sa.Integer(), nullable=True),
        sa.Column("custom_attributes", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("router_id", name="uq_nas_config_router"),
    )
    op.create_index("ix_nas_configs_router_id", "nas_configs", ["router_id"])

    op.create_table(
        "radius_dictionaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vendor_name", sa.String(length=100), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("attribute_name", sa.String(length=100), nullable=False),
        sa.Column("attribute_type", sa.Integer(), nullable=False),
        sa.Column("attribute_value_type", sa.String(length=50), nullable=False, server_default="string"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("vendor_id", "attribute_type", name="uq_radius_dict_attr"),
    )

    # ---------------------------------------------------------------------
    # Project template tables
    # ---------------------------------------------------------------------
    op.create_table(
        "project_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_type", sa.String(length=100), nullable=True),
        sa.Column("default_priority", project_priority_enum, nullable=True),
        sa.Column("estimated_duration_days", sa.Integer(), nullable=True),
        sa.Column("default_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_project_templates_is_active", "project_templates", ["is_active"])
    op.create_index("ix_project_templates_company", "project_templates", ["company"])

    op.create_table(
        "milestone_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_template_id",
            sa.Integer(),
            sa.ForeignKey("project_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_day_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("end_day_offset", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_milestone_templates_project_template_id",
        "milestone_templates",
        ["project_template_id"],
    )

    op.create_table(
        "task_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_template_id",
            sa.Integer(),
            sa.ForeignKey("project_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=50), nullable=True),
        sa.Column("start_day_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("default_assigned_role", sa.String(length=100), nullable=True),
        sa.Column("parent_template_id", sa.Integer(), sa.ForeignKey("task_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("milestone_template_id", sa.Integer(), sa.ForeignKey("milestone_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_group", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_task_templates_project_template_id",
        "task_templates",
        ["project_template_id"],
    )
    op.create_index(
        "ix_task_templates_parent_template_id",
        "task_templates",
        ["parent_template_id"],
    )
    op.create_index(
        "ix_task_templates_milestone_template_id",
        "task_templates",
        ["milestone_template_id"],
    )

    # ---------------------------------------------------------------------
    # Service transactions
    # ---------------------------------------------------------------------
    op.create_table(
        "service_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "party_id",
            sa.BigInteger(),
            sa.ForeignKey("parties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("transaction_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="NGN"),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("credit_note_id", sa.Integer(), sa.ForeignKey("credit_notes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("old_value", sa.String(length=255), nullable=True),
        sa.Column("new_value", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_service_transactions_subscription_id", "service_transactions", ["subscription_id"])
    op.create_index("ix_service_transactions_party_id", "service_transactions", ["party_id"])
    op.create_index("ix_service_transactions_transaction_type", "service_transactions", ["transaction_type"])
    op.create_index("ix_service_transactions_status", "service_transactions", ["status"])
    op.create_index("ix_service_transactions_effective_date", "service_transactions", ["effective_date"])
    op.create_index("ix_service_transactions_invoice_id", "service_transactions", ["invoice_id"])
    op.create_index(
        "ix_service_transactions_sub_type",
        "service_transactions",
        ["subscription_id", "transaction_type"],
    )
    op.create_index(
        "ix_service_transactions_party_date",
        "service_transactions",
        ["party_id", "effective_date"],
    )
    op.create_index(
        "ix_service_transactions_type_date",
        "service_transactions",
        ["transaction_type", "effective_date"],
    )


def downgrade() -> None:
    # Drop service transactions
    op.drop_index("ix_service_transactions_type_date", table_name="service_transactions")
    op.drop_index("ix_service_transactions_party_date", table_name="service_transactions")
    op.drop_index("ix_service_transactions_sub_type", table_name="service_transactions")
    op.drop_index("ix_service_transactions_invoice_id", table_name="service_transactions")
    op.drop_index("ix_service_transactions_effective_date", table_name="service_transactions")
    op.drop_index("ix_service_transactions_status", table_name="service_transactions")
    op.drop_index("ix_service_transactions_transaction_type", table_name="service_transactions")
    op.drop_index("ix_service_transactions_party_id", table_name="service_transactions")
    op.drop_index("ix_service_transactions_subscription_id", table_name="service_transactions")
    op.drop_table("service_transactions")

    # Drop project template tables
    op.drop_index("ix_task_templates_milestone_template_id", table_name="task_templates")
    op.drop_index("ix_task_templates_parent_template_id", table_name="task_templates")
    op.drop_index("ix_task_templates_project_template_id", table_name="task_templates")
    op.drop_table("task_templates")
    op.drop_index("ix_milestone_templates_project_template_id", table_name="milestone_templates")
    op.drop_table("milestone_templates")
    op.drop_index("ix_project_templates_company", table_name="project_templates")
    op.drop_index("ix_project_templates_is_active", table_name="project_templates")
    op.drop_table("project_templates")

    # Drop RADIUS tables
    op.drop_index("ix_nas_configs_router_id", table_name="nas_configs")
    op.drop_table("nas_configs")
    op.drop_index("ix_radius_attribute_mappings_company", table_name="radius_attribute_mappings")
    op.drop_table("radius_attribute_mappings")
    op.drop_index("ix_radius_settings_company", table_name="radius_settings")
    op.drop_table("radius_settings")
    op.drop_table("radius_dictionaries")

    # Drop tax tables
    op.drop_index("ix_tax_transactions_source", table_name="tax_transactions")
    op.drop_index("ix_tax_transactions_company_period", table_name="tax_transactions")
    op.drop_index("ix_tax_transactions_period", table_name="tax_transactions")
    op.drop_index("ix_tax_transactions_status", table_name="tax_transactions")
    op.drop_index("ix_tax_transactions_filing_period", table_name="tax_transactions")
    op.drop_index("ix_tax_transactions_company", table_name="tax_transactions")
    op.drop_index("ix_tax_transactions_transaction_date", table_name="tax_transactions")
    op.drop_index("ix_tax_transactions_transaction_type", table_name="tax_transactions")
    op.drop_index("ix_tax_transactions_reference_number", table_name="tax_transactions")
    op.drop_index("ix_tax_transactions_category_id", table_name="tax_transactions")
    op.drop_index("ix_tax_transactions_region_id", table_name="tax_transactions")
    op.drop_table("tax_transactions")
    op.drop_index("ix_tax_rates_category_effective", table_name="tax_rates")
    op.drop_index("ix_tax_rates_category_id", table_name="tax_rates")
    op.drop_table("tax_rates")
    op.drop_index("ix_generic_tax_categories_category_type", table_name="generic_tax_categories")
    op.drop_index("ix_generic_tax_categories_code", table_name="generic_tax_categories")
    op.drop_index("ix_generic_tax_categories_region", table_name="generic_tax_categories")
    op.drop_table("generic_tax_categories")

    # Drop enum types created in this migration
    op.execute("DROP TYPE IF EXISTS taxtransactionstatus")
    op.execute("DROP TYPE IF EXISTS taxtransactiontype")
    op.execute("DROP TYPE IF EXISTS taxcategorytype")
    op.execute("DROP TYPE IF EXISTS sessionlimitaction")
    op.execute("DROP TYPE IF EXISTS bandwidthunit")
    op.execute("DROP TYPE IF EXISTS accountingmethod")
    op.execute("DROP TYPE IF EXISTS passwordencryption")
    op.execute("DROP TYPE IF EXISTS authenticationtype")
    op.execute("DROP TYPE IF EXISTS nastype")
