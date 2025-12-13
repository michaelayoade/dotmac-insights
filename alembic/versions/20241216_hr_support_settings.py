"""HR and Support settings infrastructure

Revision ID: 20241216_hr_support_settings
Revises: 20241215_merge_books_payroll
Create Date: 2024-12-16

Adds comprehensive settings infrastructure for HR and Support modules:
- hr_settings: Company-wide HR configuration
- leave_encashment_policies: Leave encashment rules by type
- holiday_calendars & holidays: Holiday management
- salary_bands: Salary ranges by grade
- document_checklist_templates: Onboarding/separation checklists
- support_settings: Company-wide support configuration
- escalation_policies & escalation_levels: Multi-level escalation
- support_queues: Custom ticket queues
- ticket_field_configs: Custom ticket fields
- support_email_templates: Email notification templates
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241216_hr_support_settings"
down_revision: Union[str, None] = "20241215_merge_books_payroll"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # HR ENUMS
    # ==========================================================================
    op.execute("CREATE TYPE leaveaccountingfrequency AS ENUM ('ANNUAL', 'MONTHLY', 'QUARTERLY', 'BIANNUAL')")
    op.execute("CREATE TYPE proratamethod AS ENUM ('LINEAR', 'CALENDAR_DAYS', 'WORKING_DAYS', 'MONTHLY')")
    op.execute("CREATE TYPE payrollfrequency AS ENUM ('WEEKLY', 'BIWEEKLY', 'MONTHLY', 'SEMIMONTHLY')")
    op.execute("CREATE TYPE overtimecalculation AS ENUM ('HOURLY_RATE', 'DAILY_RATE', 'MONTHLY_RATE')")
    op.execute("CREATE TYPE gratuitycalculation AS ENUM ('LAST_SALARY', 'AVERAGE_SALARY', 'BASIC_SALARY')")
    op.execute("CREATE TYPE employeeidformat AS ENUM ('NUMERIC', 'ALPHANUMERIC', 'YEAR_BASED', 'DEPARTMENT_BASED')")
    op.execute("CREATE TYPE attendancemarkingmode AS ENUM ('MANUAL', 'BIOMETRIC', 'GEOLOCATION', 'HYBRID')")
    op.execute("CREATE TYPE appraisalfrequency AS ENUM ('ANNUAL', 'SEMIANNUAL', 'QUARTERLY', 'MONTHLY')")

    # ==========================================================================
    # HR SETTINGS
    # ==========================================================================
    op.create_table(
        "hr_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=True, unique=True, index=True),

        # Leave Policy
        sa.Column("leave_accounting_frequency", postgresql.ENUM("ANNUAL", "MONTHLY", "QUARTERLY", "BIANNUAL", name="leaveaccountingfrequency", create_type=False), nullable=False, server_default="ANNUAL"),
        sa.Column("pro_rata_method", postgresql.ENUM("LINEAR", "CALENDAR_DAYS", "WORKING_DAYS", "MONTHLY", name="proratamethod", create_type=False), nullable=False, server_default="WORKING_DAYS"),
        sa.Column("max_carryforward_days", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("carryforward_expiry_months", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("min_leave_notice_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("allow_negative_leave_balance", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("allow_leave_overlap", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("sick_leave_auto_approve_days", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("medical_certificate_required_after_days", sa.Integer(), nullable=False, server_default="2"),

        # Attendance
        sa.Column("attendance_marking_mode", postgresql.ENUM("MANUAL", "BIOMETRIC", "GEOLOCATION", "HYBRID", name="attendancemarkingmode", create_type=False), nullable=False, server_default="MANUAL"),
        sa.Column("allow_backdated_attendance", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("backdated_attendance_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("auto_mark_absent_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("auto_absent_cutoff_time", sa.Time(), nullable=True),
        sa.Column("late_entry_grace_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("early_exit_grace_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("half_day_hours_threshold", sa.Numeric(4, 2), nullable=False, server_default="4.00"),
        sa.Column("full_day_hours_threshold", sa.Numeric(4, 2), nullable=False, server_default="8.00"),
        sa.Column("require_checkout", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("geolocation_required", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("geolocation_radius_meters", sa.Integer(), nullable=False, server_default="100"),

        # Shift
        sa.Column("default_shift_id", sa.Integer(), sa.ForeignKey("shift_types.id"), nullable=True),
        sa.Column("max_weekly_hours", sa.Integer(), nullable=False, server_default="48"),
        sa.Column("night_shift_allowance_percent", sa.Numeric(5, 2), nullable=False, server_default="10.00"),
        sa.Column("shift_change_notice_days", sa.Integer(), nullable=False, server_default="3"),

        # Payroll
        sa.Column("payroll_frequency", postgresql.ENUM("WEEKLY", "BIWEEKLY", "MONTHLY", "SEMIMONTHLY", name="payrollfrequency", create_type=False), nullable=False, server_default="MONTHLY"),
        sa.Column("salary_payment_day", sa.Integer(), nullable=False, server_default="28"),
        sa.Column("payroll_cutoff_day", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("allow_salary_advance", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("max_advance_percent", sa.Numeric(5, 2), nullable=False, server_default="50.00"),
        sa.Column("max_advance_months", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("salary_currency", sa.String(3), nullable=False, server_default="NGN"),

        # Overtime
        sa.Column("overtime_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("overtime_calculation", postgresql.ENUM("HOURLY_RATE", "DAILY_RATE", "MONTHLY_RATE", name="overtimecalculation", create_type=False), nullable=False, server_default="HOURLY_RATE"),
        sa.Column("overtime_multiplier_weekday", sa.Numeric(4, 2), nullable=False, server_default="1.50"),
        sa.Column("overtime_multiplier_weekend", sa.Numeric(4, 2), nullable=False, server_default="2.00"),
        sa.Column("overtime_multiplier_holiday", sa.Numeric(4, 2), nullable=False, server_default="2.50"),
        sa.Column("min_overtime_hours", sa.Numeric(4, 2), nullable=False, server_default="1.00"),
        sa.Column("require_overtime_approval", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),

        # Benefits
        sa.Column("gratuity_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("gratuity_calculation", postgresql.ENUM("LAST_SALARY", "AVERAGE_SALARY", "BASIC_SALARY", name="gratuitycalculation", create_type=False), nullable=False, server_default="LAST_SALARY"),
        sa.Column("gratuity_eligibility_years", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("gratuity_days_per_year", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("pf_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("pf_employer_percent", sa.Numeric(5, 2), nullable=False, server_default="12.00"),
        sa.Column("pf_employee_percent", sa.Numeric(5, 2), nullable=False, server_default="12.00"),
        sa.Column("pension_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("pension_employer_percent", sa.Numeric(5, 2), nullable=False, server_default="10.00"),
        sa.Column("pension_employee_percent", sa.Numeric(5, 2), nullable=False, server_default="8.00"),
        sa.Column("nhf_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("nhf_percent", sa.Numeric(5, 2), nullable=False, server_default="2.50"),

        # Lifecycle
        sa.Column("default_probation_months", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("max_probation_extension_months", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("default_notice_period_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("require_exit_interview", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("final_settlement_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("require_clearance_before_settlement", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),

        # Recruitment
        sa.Column("job_posting_validity_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("offer_validity_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("default_interview_duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("require_background_check", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("document_submission_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("allow_offer_negotiation", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("offer_negotiation_window_days", sa.Integer(), nullable=False, server_default="3"),

        # Appraisal
        sa.Column("appraisal_frequency", postgresql.ENUM("ANNUAL", "SEMIANNUAL", "QUARTERLY", "MONTHLY", name="appraisalfrequency", create_type=False), nullable=False, server_default="ANNUAL"),
        sa.Column("appraisal_cycle_start_month", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("appraisal_rating_scale", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("require_self_review", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("require_peer_review", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("enable_360_feedback", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("min_rating_for_promotion", sa.Numeric(3, 1), nullable=False, server_default="4.0"),

        # Training
        sa.Column("mandatory_training_hours_yearly", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("require_training_approval", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("training_completion_threshold_percent", sa.Integer(), nullable=False, server_default="80"),

        # Compliance
        sa.Column("work_week_days", postgresql.JSON(), nullable=False, server_default='["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]'),
        sa.Column("standard_work_hours_per_day", sa.Numeric(4, 2), nullable=False, server_default="8.00"),
        sa.Column("max_work_hours_per_day", sa.Integer(), nullable=False, server_default="12"),

        # Display
        sa.Column("employee_id_format", postgresql.ENUM("NUMERIC", "ALPHANUMERIC", "YEAR_BASED", "DEPARTMENT_BASED", name="employeeidformat", create_type=False), nullable=False, server_default="NUMERIC"),
        sa.Column("employee_id_prefix", sa.String(10), nullable=False, server_default="EMP"),
        sa.Column("employee_id_min_digits", sa.Integer(), nullable=False, server_default="4"),

        # Notifications
        sa.Column("notify_leave_balance_below", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("notify_appraisal_due_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("notify_probation_end_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("notify_contract_expiry_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("notify_document_expiry_days", sa.Integer(), nullable=False, server_default="30"),

        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # ==========================================================================
    # LEAVE ENCASHMENT POLICIES
    # ==========================================================================
    op.create_table(
        "leave_encashment_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=True, index=True),
        sa.Column("leave_type_id", sa.Integer(), sa.ForeignKey("leave_types.id"), nullable=False, index=True),
        sa.Column("is_encashable", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("max_encashment_days_yearly", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_balance_to_encash", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("encashment_rate_percent", sa.Numeric(5, 2), nullable=False, server_default="100.00"),
        sa.Column("allow_partial_encashment", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("encash_on_separation", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("taxable", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true(), index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company", "leave_type_id", name="uq_encashment_policy_company_leave_type"),
    )

    # ==========================================================================
    # HOLIDAY CALENDARS
    # ==========================================================================
    op.create_table(
        "holiday_calendars",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("company", sa.String(255), nullable=True, index=True),
        sa.Column("location", sa.String(255), nullable=True, index=True),
        sa.Column("year", sa.Integer(), nullable=False, index=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true(), index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("company", "location", "year", name="uq_holiday_calendar_company_location_year"),
    )

    op.create_table(
        "hr_holidays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("calendar_id", sa.Integer(), sa.ForeignKey("holiday_calendars.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("calendar_id", "date", name="uq_hr_holiday_calendar_date"),
    )

    # ==========================================================================
    # SALARY BANDS
    # ==========================================================================
    op.create_table(
        "salary_bands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("grade", sa.String(50), nullable=True, index=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("min_salary", sa.Numeric(18, 2), nullable=False),
        sa.Column("max_salary", sa.Numeric(18, 2), nullable=False),
        sa.Column("mid_salary", sa.Numeric(18, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true(), index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company", "name", name="uq_salary_band_company_name"),
    )

    # ==========================================================================
    # DOCUMENT CHECKLIST TEMPLATES
    # ==========================================================================
    op.create_table(
        "document_checklist_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("template_type", sa.String(20), nullable=False, index=True),
        sa.Column("items", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true(), index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("company", "name", "template_type", name="uq_checklist_template_company_name_type"),
    )

    # ==========================================================================
    # SUPPORT ENUMS
    # ==========================================================================
    op.execute("CREATE TYPE workinghourstype AS ENUM ('STANDARD', 'EXTENDED', 'ROUND_THE_CLOCK', 'CUSTOM')")
    op.execute("CREATE TYPE defaultroutingstrategy AS ENUM ('ROUND_ROBIN', 'LEAST_BUSY', 'SKILL_BASED', 'LOAD_BALANCED', 'MANUAL')")
    op.execute("CREATE TYPE ticketautocloseaction AS ENUM ('CLOSE', 'ARCHIVE', 'NOTIFY_ONLY')")
    op.execute("CREATE TYPE csatsurveytrigger AS ENUM ('ON_RESOLVE', 'ON_CLOSE', 'MANUAL', 'DISABLED')")
    op.execute("CREATE TYPE escalationtrigger AS ENUM ('SLA_BREACH', 'SLA_WARNING', 'IDLE_TIME', 'CUSTOMER_ESCALATION', 'REOPEN_COUNT')")
    op.execute("CREATE TYPE ticketprioritydefault AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'URGENT')")

    # ==========================================================================
    # SUPPORT SETTINGS
    # ==========================================================================
    op.create_table(
        "support_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=True, unique=True, index=True),

        # Business Hours
        sa.Column("working_hours_type", postgresql.ENUM("STANDARD", "EXTENDED", "ROUND_THE_CLOCK", "CUSTOM", name="workinghourstype", create_type=False), nullable=False, server_default="STANDARD"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Africa/Lagos"),
        sa.Column("weekly_schedule", postgresql.JSON(), nullable=False, server_default='{"MONDAY": {"start": "09:00", "end": "17:00", "closed": false}, "TUESDAY": {"start": "09:00", "end": "17:00", "closed": false}, "WEDNESDAY": {"start": "09:00", "end": "17:00", "closed": false}, "THURSDAY": {"start": "09:00", "end": "17:00", "closed": false}, "FRIDAY": {"start": "09:00", "end": "17:00", "closed": false}, "SATURDAY": {"start": "00:00", "end": "00:00", "closed": true}, "SUNDAY": {"start": "00:00", "end": "00:00", "closed": true}}'),
        sa.Column("holiday_calendar_id", sa.Integer(), nullable=True),

        # SLA Defaults
        sa.Column("default_sla_policy_id", sa.Integer(), sa.ForeignKey("sla_policies.id"), nullable=True),
        sa.Column("sla_warning_threshold_percent", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("sla_include_holidays", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("sla_include_weekends", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("default_first_response_hours", sa.Numeric(6, 2), nullable=False, server_default="4.00"),
        sa.Column("default_resolution_hours", sa.Numeric(6, 2), nullable=False, server_default="24.00"),

        # Ticket Routing
        sa.Column("default_routing_strategy", postgresql.ENUM("ROUND_ROBIN", "LEAST_BUSY", "SKILL_BASED", "LOAD_BALANCED", "MANUAL", name="defaultroutingstrategy", create_type=False), nullable=False, server_default="ROUND_ROBIN"),
        sa.Column("default_team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("fallback_team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("auto_assign_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("max_tickets_per_agent", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("rebalance_threshold_percent", sa.Integer(), nullable=False, server_default="30"),

        # Ticket Defaults
        sa.Column("default_priority", postgresql.ENUM("LOW", "MEDIUM", "HIGH", "URGENT", name="ticketprioritydefault", create_type=False), nullable=False, server_default="MEDIUM"),
        sa.Column("default_ticket_type", sa.String(50), nullable=True),
        sa.Column("allow_customer_priority_selection", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("allow_customer_team_selection", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),

        # Auto-Close
        sa.Column("auto_close_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("auto_close_resolved_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("auto_close_action", postgresql.ENUM("CLOSE", "ARCHIVE", "NOTIFY_ONLY", name="ticketautocloseaction", create_type=False), nullable=False, server_default="CLOSE"),
        sa.Column("auto_close_notify_customer", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("allow_customer_reopen", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("reopen_window_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("max_reopens_allowed", sa.Integer(), nullable=False, server_default="3"),

        # Escalation
        sa.Column("escalation_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("default_escalation_team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("escalation_notify_manager", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("idle_escalation_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("idle_hours_before_escalation", sa.Integer(), nullable=False, server_default="48"),
        sa.Column("reopen_escalation_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("reopen_count_for_escalation", sa.Integer(), nullable=False, server_default="2"),

        # CSAT
        sa.Column("csat_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("csat_survey_trigger", postgresql.ENUM("ON_RESOLVE", "ON_CLOSE", "MANUAL", "DISABLED", name="csatsurveytrigger", create_type=False), nullable=False, server_default="ON_RESOLVE"),
        sa.Column("csat_delay_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("csat_reminder_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("csat_reminder_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("csat_survey_expiry_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("default_csat_survey_id", sa.Integer(), sa.ForeignKey("csat_surveys.id"), nullable=True),

        # Customer Portal
        sa.Column("portal_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("portal_ticket_creation_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("portal_show_ticket_history", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("portal_show_knowledge_base", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("portal_show_faq", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("portal_require_login", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),

        # Knowledge Base
        sa.Column("kb_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("kb_public_access", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("kb_suggest_articles_on_create", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("kb_track_article_helpfulness", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),

        # Notifications
        sa.Column("notification_channels", postgresql.JSON(), nullable=False, server_default='["EMAIL", "IN_APP"]'),
        sa.Column("notification_events", postgresql.JSON(), nullable=False, server_default='{"ticket_created": true, "ticket_assigned": true, "ticket_replied": true, "ticket_resolved": true, "ticket_closed": true, "ticket_reopened": true, "sla_warning": true, "sla_breach": true, "ticket_escalated": true, "customer_replied": true}'),
        sa.Column("notify_assigned_agent", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("notify_team_on_unassigned", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("notify_customer_on_status_change", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("notify_customer_on_reply", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),

        # Queue Management
        sa.Column("unassigned_warning_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("overdue_highlight_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("queue_refresh_seconds", sa.Integer(), nullable=False, server_default="60"),

        # Integrations
        sa.Column("email_to_ticket_enabled", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("email_reply_to_address", sa.String(255), nullable=True),
        sa.Column("sync_to_erpnext", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("sync_to_splynx", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("sync_to_chatwoot", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),

        # Data Retention
        sa.Column("archive_closed_tickets_days", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("delete_archived_tickets_days", sa.Integer(), nullable=False, server_default="0"),

        # Display
        sa.Column("ticket_id_prefix", sa.String(10), nullable=False, server_default="TKT"),
        sa.Column("ticket_id_min_digits", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("date_format", sa.String(20), nullable=False, server_default="DD/MM/YYYY"),
        sa.Column("time_format", sa.String(10), nullable=False, server_default="HH:mm"),

        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    # ==========================================================================
    # ESCALATION POLICIES
    # ==========================================================================
    op.create_table(
        "escalation_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("conditions", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true(), index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("company", "name", name="uq_escalation_policy_company_name"),
    )

    op.create_table(
        "escalation_levels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("escalation_policies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("trigger", postgresql.ENUM("SLA_BREACH", "SLA_WARNING", "IDLE_TIME", "CUSTOMER_ESCALATION", "REOPEN_COUNT", name="escalationtrigger", create_type=False), nullable=False, server_default="SLA_BREACH"),
        sa.Column("trigger_hours", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("escalate_to_team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("escalate_to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notify_current_assignee", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("notify_team_lead", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("reassign_ticket", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("change_priority", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("new_priority", sa.String(20), nullable=True),
        sa.Column("notification_template", sa.Text(), nullable=True),
        sa.UniqueConstraint("policy_id", "level", name="uq_escalation_level_policy_level"),
    )

    # ==========================================================================
    # SUPPORT QUEUES
    # ==========================================================================
    op.create_table(
        "support_queues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("queue_type", sa.String(20), nullable=False, server_default="CUSTOM"),
        sa.Column("filters", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("sort_by", sa.String(50), nullable=False, server_default="created_at"),
        sa.Column("sort_direction", sa.String(4), nullable=False, server_default="DESC"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true(), index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company", "name", name="uq_support_queue_company_name"),
    )

    # ==========================================================================
    # TICKET FIELD CONFIGS
    # ==========================================================================
    op.create_table(
        "ticket_field_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=True, index=True),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("field_key", sa.String(50), nullable=False),
        sa.Column("field_type", sa.String(20), nullable=False),
        sa.Column("options", postgresql.JSON(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("min_length", sa.Integer(), nullable=True),
        sa.Column("max_length", sa.Integer(), nullable=True),
        sa.Column("validation_regex", sa.String(255), nullable=True),
        sa.Column("default_value", sa.String(255), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("show_in_list", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("show_in_create_form", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("show_in_customer_portal", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("applies_to_types", postgresql.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true(), index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company", "field_key", name="uq_ticket_field_config_company_key"),
    )

    # ==========================================================================
    # SUPPORT EMAIL TEMPLATES
    # ==========================================================================
    op.create_table(
        "support_email_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String(255), nullable=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("template_type", sa.String(50), nullable=False, index=True),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("supported_placeholders", postgresql.JSON(), nullable=False, server_default='["{{ticket_id}}", "{{ticket_subject}}", "{{customer_name}}", "{{agent_name}}", "{{ticket_status}}", "{{ticket_priority}}", "{{company_name}}", "{{portal_url}}", "{{ticket_url}}"]'),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true(), index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company", "template_type", name="uq_support_email_template_company_type"),
    )


def downgrade() -> None:
    # Drop support tables
    op.drop_table("support_email_templates")
    op.drop_table("ticket_field_configs")
    op.drop_table("support_queues")
    op.drop_table("escalation_levels")
    op.drop_table("escalation_policies")
    op.drop_table("support_settings")

    # Drop support enums
    op.execute("DROP TYPE IF EXISTS ticketprioritydefault")
    op.execute("DROP TYPE IF EXISTS escalationtrigger")
    op.execute("DROP TYPE IF EXISTS csatsurveytrigger")
    op.execute("DROP TYPE IF EXISTS ticketautocloseaction")
    op.execute("DROP TYPE IF EXISTS defaultroutingstrategy")
    op.execute("DROP TYPE IF EXISTS workinghourstype")

    # Drop HR tables
    op.drop_table("document_checklist_templates")
    op.drop_table("salary_bands")
    op.drop_table("hr_holidays")
    op.drop_table("holiday_calendars")
    op.drop_table("leave_encashment_policies")
    op.drop_table("hr_settings")

    # Drop HR enums
    op.execute("DROP TYPE IF EXISTS appraisalfrequency")
    op.execute("DROP TYPE IF EXISTS attendancemarkingmode")
    op.execute("DROP TYPE IF EXISTS employeeidformat")
    op.execute("DROP TYPE IF EXISTS gratuitycalculation")
    op.execute("DROP TYPE IF EXISTS overtimecalculation")
    op.execute("DROP TYPE IF EXISTS payrollfrequency")
    op.execute("DROP TYPE IF EXISTS proratamethod")
    op.execute("DROP TYPE IF EXISTS leaveaccountingfrequency")
