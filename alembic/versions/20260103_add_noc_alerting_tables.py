"""Add NOC alerting tables

Tables for network monitoring alerts, incidents, and traffic metrics.

Revision ID: f9a3b7c2d5e8
Revises: snmp001_add_monitoring
Create Date: 2026-01-03 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f9a3b7c2d5e8"
down_revision: Union[str, None] = "snmp001_add_monitoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========================================================================
    # Alert Rules Table
    # ========================================================================
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("alert_type", sa.String(50), nullable=False, index=True),
        sa.Column("severity", sa.String(20), server_default="warning"),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("routers.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("pop_id", sa.Integer(), sa.ForeignKey("pops.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("interface_pattern", sa.String(100), nullable=True),
        sa.Column("threshold_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("threshold_operator", sa.String(10), server_default="gt"),
        sa.Column("threshold_duration_seconds", sa.Integer(), server_default="0"),
        sa.Column("cooldown_seconds", sa.Integer(), server_default="300"),
        sa.Column("notification_config", sa.JSON(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", index=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alert_rules_enabled_type "
        "ON alert_rules (is_enabled, alert_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alert_rules_scope "
        "ON alert_rules (router_id, pop_id)"
    )

    # ========================================================================
    # Alerts Table
    # ========================================================================
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("alert_type", sa.String(50), nullable=False, index=True),
        sa.Column("severity", sa.String(20), nullable=False, index=True),
        sa.Column("status", sa.String(20), server_default="active", index=True),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("routers.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("pop_id", sa.Integer(), sa.ForeignKey("pops.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("interface_index", sa.Integer(), nullable=True),
        sa.Column("interface_name", sa.String(100), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=True),
        sa.Column("metric_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("threshold_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("triggered_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("first_occurrence_at", sa.DateTime(), nullable=False),
        sa.Column("last_occurrence_at", sa.DateTime(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), server_default="1"),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_by_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("acknowledgement_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("auto_resolved", sa.Boolean(), server_default="false"),
        sa.Column("incident_id", sa.Integer(), nullable=True),  # FK added after network_incidents table
        sa.Column("suppressed_until", sa.DateTime(), nullable=True),
        sa.Column("suppression_reason", sa.String(255), nullable=True),
        sa.Column("notification_sent_at", sa.DateTime(), nullable=True),
        sa.Column("notification_channels", sa.JSON(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alerts_status_severity "
        "ON alerts (status, severity)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alerts_active_router "
        "ON alerts (status, router_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alerts_triggered_at "
        "ON alerts (triggered_at)"
    )

    # ========================================================================
    # Alert Escalations Table
    # ========================================================================
    op.create_table(
        "alert_escalations",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("escalate_after_minutes", sa.Integer(), nullable=False),
        sa.Column("notification_config", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_alert_escalations_rule_level "
        "ON alert_escalations (rule_id, level)"
    )

    # ========================================================================
    # Alert Suppressions Table (Maintenance Windows)
    # ========================================================================
    op.create_table(
        "alert_suppressions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("routers.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("pop_id", sa.Integer(), sa.ForeignKey("pops.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("alert_types", sa.JSON(), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("ends_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=True),  # FK added after network_incidents table
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alert_suppressions_active "
        "ON alert_suppressions (starts_at, ends_at)"
    )

    # ========================================================================
    # Network Incidents Table
    # ========================================================================
    op.create_table(
        "network_incidents",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(20), server_default="minor", index=True),
        sa.Column("status", sa.String(20), server_default="investigating", index=True),
        sa.Column("incident_type", sa.String(50), nullable=True),
        sa.Column("affected_pop_ids", sa.JSON(), nullable=True),
        sa.Column("affected_router_ids", sa.JSON(), nullable=True),
        sa.Column("affected_interface_names", sa.JSON(), nullable=True),
        sa.Column("affected_subscription_count", sa.Integer(), server_default="0"),
        sa.Column("estimated_customer_count", sa.Integer(), server_default="0"),
        sa.Column("estimated_revenue_impact", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("detected_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("scheduled_end_at", sa.DateTime(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("root_cause_category", sa.String(100), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolution_time_minutes", sa.Integer(), nullable=True),
        sa.Column("public_title", sa.String(255), nullable=True),
        sa.Column("public_description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default="false"),
        sa.Column("auto_detected", sa.Boolean(), server_default="false"),
        sa.Column("auto_resolved", sa.Boolean(), server_default="false"),
        sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True, index=True),
        sa.Column("external_ticket_id", sa.String(100), nullable=True),
        sa.Column("source_alert_ids", sa.JSON(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_network_incidents_status_severity "
        "ON network_incidents (status, severity)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_network_incidents_started_at "
        "ON network_incidents (started_at)"
    )

    # Now add the FK constraints that reference network_incidents
    op.create_foreign_key(
        "fk_alerts_incident_id",
        "alerts", "network_incidents",
        ["incident_id"], ["id"],
        ondelete="SET NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alerts_incident_id "
        "ON alerts (incident_id)"
    )

    op.create_foreign_key(
        "fk_alert_suppressions_incident_id",
        "alert_suppressions", "network_incidents",
        ["incident_id"], ["id"],
        ondelete="SET NULL"
    )

    # ========================================================================
    # Incident Updates Table
    # ========================================================================
    op.create_table(
        "incident_updates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("network_incidents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default="false"),
        sa.Column("public_message", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # ========================================================================
    # Incident Affected Subscriptions Table
    # ========================================================================
    op.create_table(
        "incident_affected_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("network_incidents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("impact_start", sa.DateTime(), nullable=False),
        sa.Column("impact_end", sa.DateTime(), nullable=True),
        sa.Column("downtime_minutes", sa.Integer(), nullable=True),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
        sa.Column("notification_channel", sa.String(50), nullable=True),
        sa.Column("sla_credit_applied", sa.Boolean(), server_default="false"),
        sa.Column("credit_amount", sa.Float(), nullable=True),
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_incident_affected_subs_incident_sub "
        "ON incident_affected_subscriptions (incident_id, subscription_id)"
    )

    # ========================================================================
    # Traffic Metrics Table
    # ========================================================================
    op.create_table(
        "traffic_metrics",
        sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("routers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("interface", sa.String(100), nullable=False, index=True),
        sa.Column("interface_index", sa.Integer(), nullable=True),
        sa.Column("interface_type", sa.String(50), nullable=True),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("rx_bytes", sa.BigInteger(), server_default="0"),
        sa.Column("tx_bytes", sa.BigInteger(), server_default="0"),
        sa.Column("rx_rate", sa.BigInteger(), server_default="0"),
        sa.Column("tx_rate", sa.BigInteger(), server_default="0"),
        sa.Column("rx_packets", sa.BigInteger(), nullable=True),
        sa.Column("tx_packets", sa.BigInteger(), nullable=True),
        sa.Column("rx_errors", sa.BigInteger(), nullable=True),
        sa.Column("tx_errors", sa.BigInteger(), nullable=True),
        sa.Column("rx_drops", sa.BigInteger(), nullable=True),
        sa.Column("tx_drops", sa.BigInteger(), nullable=True),
        sa.Column("oper_status", sa.String(20), nullable=True),
        sa.Column("admin_status", sa.String(20), nullable=True),
        sa.Column("aggregation", sa.String(20), server_default="raw"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_traffic_metrics_router_timestamp "
        "ON traffic_metrics (router_id, timestamp)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_traffic_metrics_interface_timestamp "
        "ON traffic_metrics (interface, timestamp)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_traffic_metrics_aggregation_timestamp "
        "ON traffic_metrics (aggregation, timestamp)"
    )

    # ========================================================================
    # Traffic Thresholds Table
    # ========================================================================
    op.create_table(
        "traffic_thresholds",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("routers.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("interface", sa.String(100), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("operator", sa.String(10), server_default="gt"),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), server_default="300"),
        sa.Column("severity", sa.String(20), server_default="warning"),
        sa.Column("notification_channels", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", index=True),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("trigger_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ========================================================================
    # Traffic Alerts Table
    # ========================================================================
    op.create_table(
        "traffic_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("threshold_id", sa.Integer(), sa.ForeignKey("traffic_thresholds.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("routers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("interface", sa.String(100), nullable=False),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("threshold_value", sa.BigInteger(), nullable=False),
        sa.Column("actual_value", sa.BigInteger(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", index=True),
        sa.Column("acknowledged_by_id", sa.Integer(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_traffic_alerts_status_triggered "
        "ON traffic_alerts (status, triggered_at)"
    )


def downgrade() -> None:
    # Drop tables in reverse order of creation (respecting dependencies)
    op.drop_table("traffic_alerts")
    op.drop_table("traffic_thresholds")
    op.drop_table("traffic_metrics")
    op.drop_table("incident_affected_subscriptions")
    op.drop_table("incident_updates")

    # Drop FK constraints from alerts and alert_suppressions
    op.drop_constraint("fk_alerts_incident_id", "alerts", type_="foreignkey")
    op.drop_index("ix_alerts_incident_id", "alerts")
    op.drop_constraint("fk_alert_suppressions_incident_id", "alert_suppressions", type_="foreignkey")

    op.drop_table("network_incidents")
    op.drop_table("alert_suppressions")
    op.drop_table("alert_escalations")
    op.drop_table("alerts")
    op.drop_table("alert_rules")
