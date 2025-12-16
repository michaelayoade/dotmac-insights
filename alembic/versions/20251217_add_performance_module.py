"""Add performance module tables with seed KPI/KRA data

Revision ID: perf001_performance_module
Revises: uc002_migrate_contacts
Create Date: 2025-12-17

Creates 14 tables for the Performance Management Module:
- evaluation_periods: Evaluation windows (monthly, quarterly, annual)
- kra_definitions: Key Result Area definitions
- kpi_definitions: KPI definitions with scoring config
- kra_kpi_map: KRA to KPI mappings with weights
- scorecard_templates: Scorecard templates per role/department
- scorecard_template_items: KRAs assigned to templates
- kpi_bindings: Employee/department-specific target overrides
- employee_scorecard_instances: Employee scorecards per period
- kpi_results: Computed KPI results
- kra_results: Computed KRA results
- score_overrides: Audit log for score changes
- performance_review_notes: Review comments
- bonus_policies: Bonus calculation bands
- performance_snapshots: Analytics snapshots
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = 'perf001_performance_module'
down_revision = 'uc002_migrate_contacts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # EVALUATION PERIODS
    # =========================================================================
    op.create_table(
        'evaluation_periods',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('period_type', sa.String(50), nullable=False),  # monthly, quarterly, etc
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('scoring_deadline', sa.Date(), nullable=True),
        sa.Column('review_deadline', sa.Date(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_evaluation_periods_code', 'evaluation_periods', ['code'], unique=True)
    op.create_index('ix_evaluation_periods_status', 'evaluation_periods', ['status'])
    op.create_index('ix_evaluation_periods_start_date', 'evaluation_periods', ['start_date'])

    # =========================================================================
    # KRA DEFINITIONS
    # =========================================================================
    op.create_table(
        'kra_definitions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_kra_definitions_code', 'kra_definitions', ['code'], unique=True)
    op.create_index('ix_kra_definitions_category', 'kra_definitions', ['category'])

    # =========================================================================
    # KPI DEFINITIONS
    # =========================================================================
    op.create_table(
        'kpi_definitions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('data_source', sa.String(50), nullable=False),  # manual, ticketing, field_service, etc
        sa.Column('aggregation', sa.String(50), nullable=False),  # sum, avg, count, percent, ratio
        sa.Column('query_config', sa.JSON(), nullable=True),
        sa.Column('scoring_method', sa.String(50), nullable=False),  # linear, threshold, band, binary
        sa.Column('min_value', sa.Numeric(18, 4), nullable=True),
        sa.Column('target_value', sa.Numeric(18, 4), nullable=True),
        sa.Column('max_value', sa.Numeric(18, 4), nullable=True),
        sa.Column('threshold_config', sa.JSON(), nullable=True),
        sa.Column('higher_is_better', sa.Boolean(), default=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_kpi_definitions_code', 'kpi_definitions', ['code'], unique=True)
    op.create_index('ix_kpi_definitions_data_source', 'kpi_definitions', ['data_source'])

    # =========================================================================
    # KRA - KPI MAPPING
    # =========================================================================
    op.create_table(
        'kra_kpi_map',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('kra_id', sa.Integer(), sa.ForeignKey('kra_definitions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kpi_id', sa.Integer(), sa.ForeignKey('kpi_definitions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('weightage', sa.Numeric(5, 2), default=0),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_kra_kpi_map_kra_id', 'kra_kpi_map', ['kra_id'])
    op.create_index('ix_kra_kpi_map_kpi_id', 'kra_kpi_map', ['kpi_id'])
    op.create_index('ix_kra_kpi_unique', 'kra_kpi_map', ['kra_id', 'kpi_id'], unique=True)

    # =========================================================================
    # SCORECARD TEMPLATES
    # =========================================================================
    op.create_table(
        'scorecard_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('applicable_departments', sa.JSON(), nullable=True),
        sa.Column('applicable_designations', sa.JSON(), nullable=True),
        sa.Column('version', sa.Integer(), default=1),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_scorecard_templates_code', 'scorecard_templates', ['code'], unique=True)
    op.create_index('ix_scorecard_templates_is_active', 'scorecard_templates', ['is_active'])

    # =========================================================================
    # SCORECARD TEMPLATE ITEMS
    # =========================================================================
    op.create_table(
        'scorecard_template_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('scorecard_templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kra_id', sa.Integer(), sa.ForeignKey('kra_definitions.id'), nullable=False),
        sa.Column('weightage', sa.Numeric(5, 2), default=0),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_scorecard_template_items_template_id', 'scorecard_template_items', ['template_id'])
    op.create_index('ix_scorecard_template_items_kra_id', 'scorecard_template_items', ['kra_id'])
    op.create_index('ix_template_kra_unique', 'scorecard_template_items', ['template_id', 'kra_id'], unique=True)

    # =========================================================================
    # KPI BINDINGS (employee/department target overrides)
    # =========================================================================
    op.create_table(
        'kpi_bindings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('kpi_id', sa.Integer(), sa.ForeignKey('kpi_definitions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=True),
        sa.Column('designation_id', sa.Integer(), sa.ForeignKey('designations.id'), nullable=True),
        sa.Column('target_override', sa.Numeric(18, 4), nullable=True),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_kpi_bindings_kpi_id', 'kpi_bindings', ['kpi_id'])
    op.create_index('ix_kpi_bindings_employee_id', 'kpi_bindings', ['employee_id'])
    op.create_index('ix_kpi_bindings_department_id', 'kpi_bindings', ['department_id'])
    op.create_index('ix_kpi_bindings_kpi_employee', 'kpi_bindings', ['kpi_id', 'employee_id'])
    op.create_index('ix_kpi_bindings_kpi_department', 'kpi_bindings', ['kpi_id', 'department_id'])

    # =========================================================================
    # EMPLOYEE SCORECARD INSTANCES
    # =========================================================================
    op.create_table(
        'employee_scorecard_instances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('evaluation_period_id', sa.Integer(), sa.ForeignKey('evaluation_periods.id'), nullable=False),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('scorecard_templates.id'), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),  # pending, computing, computed, in_review, approved, disputed, finalized
        sa.Column('total_weighted_score', sa.Numeric(8, 4), nullable=True),
        sa.Column('final_rating', sa.String(50), nullable=True),
        sa.Column('reviewed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('finalized_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('finalized_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_scorecard_instances_employee_id', 'employee_scorecard_instances', ['employee_id'])
    op.create_index('ix_scorecard_instances_period_id', 'employee_scorecard_instances', ['evaluation_period_id'])
    op.create_index('ix_scorecard_instances_template_id', 'employee_scorecard_instances', ['template_id'])
    op.create_index('ix_scorecard_instances_status', 'employee_scorecard_instances', ['status'])
    op.create_index('ix_scorecard_employee_period', 'employee_scorecard_instances', ['employee_id', 'evaluation_period_id'], unique=True)

    # =========================================================================
    # KPI RESULTS
    # =========================================================================
    op.create_table(
        'kpi_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scorecard_instance_id', sa.Integer(), sa.ForeignKey('employee_scorecard_instances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kpi_id', sa.Integer(), sa.ForeignKey('kpi_definitions.id'), nullable=False),
        sa.Column('kra_id', sa.Integer(), sa.ForeignKey('kra_definitions.id'), nullable=True),
        sa.Column('raw_value', sa.Numeric(18, 4), nullable=True),
        sa.Column('target_value', sa.Numeric(18, 4), nullable=True),
        sa.Column('computed_score', sa.Numeric(8, 4), nullable=True),
        sa.Column('final_score', sa.Numeric(8, 4), nullable=True),
        sa.Column('weightage_in_kra', sa.Numeric(5, 2), nullable=True),
        sa.Column('weighted_score', sa.Numeric(8, 4), nullable=True),
        sa.Column('evidence_links', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_kpi_results_scorecard_id', 'kpi_results', ['scorecard_instance_id'])
    op.create_index('ix_kpi_results_kpi_id', 'kpi_results', ['kpi_id'])
    op.create_index('ix_kpi_results_kra_id', 'kpi_results', ['kra_id'])

    # =========================================================================
    # KRA RESULTS
    # =========================================================================
    op.create_table(
        'kra_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scorecard_instance_id', sa.Integer(), sa.ForeignKey('employee_scorecard_instances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kra_id', sa.Integer(), sa.ForeignKey('kra_definitions.id'), nullable=False),
        sa.Column('computed_score', sa.Numeric(8, 4), nullable=True),
        sa.Column('final_score', sa.Numeric(8, 4), nullable=True),
        sa.Column('weightage_in_scorecard', sa.Numeric(5, 2), nullable=True),
        sa.Column('weighted_score', sa.Numeric(8, 4), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_kra_results_scorecard_id', 'kra_results', ['scorecard_instance_id'])
    op.create_index('ix_kra_results_kra_id', 'kra_results', ['kra_id'])

    # =========================================================================
    # SCORE OVERRIDES (audit log)
    # =========================================================================
    op.create_table(
        'score_overrides',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scorecard_instance_id', sa.Integer(), sa.ForeignKey('employee_scorecard_instances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('override_type', sa.String(50), nullable=False),  # kpi, kra, overall
        sa.Column('kpi_result_id', sa.Integer(), sa.ForeignKey('kpi_results.id'), nullable=True),
        sa.Column('kra_result_id', sa.Integer(), sa.ForeignKey('kra_results.id'), nullable=True),
        sa.Column('original_score', sa.Numeric(8, 4), nullable=True),
        sa.Column('overridden_score', sa.Numeric(8, 4), nullable=True),
        sa.Column('reason', sa.String(50), nullable=False),  # data_correction, extenuating_circumstances, etc
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column('overridden_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
    )
    op.create_index('ix_score_overrides_scorecard_id', 'score_overrides', ['scorecard_instance_id'])
    op.create_index('ix_score_overrides_kpi_result_id', 'score_overrides', ['kpi_result_id'])
    op.create_index('ix_score_overrides_kra_result_id', 'score_overrides', ['kra_result_id'])

    # =========================================================================
    # PERFORMANCE REVIEW NOTES
    # =========================================================================
    op.create_table(
        'performance_review_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scorecard_instance_id', sa.Integer(), sa.ForeignKey('employee_scorecard_instances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('note_type', sa.String(50), nullable=True),  # general, improvement, recognition, etc
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('kpi_result_id', sa.Integer(), sa.ForeignKey('kpi_results.id'), nullable=True),
        sa.Column('kra_result_id', sa.Integer(), sa.ForeignKey('kra_results.id'), nullable=True),
        sa.Column('is_private', sa.Boolean(), default=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
    )
    op.create_index('ix_review_notes_scorecard_id', 'performance_review_notes', ['scorecard_instance_id'])
    op.create_index('ix_review_notes_kpi_result_id', 'performance_review_notes', ['kpi_result_id'])
    op.create_index('ix_review_notes_kra_result_id', 'performance_review_notes', ['kra_result_id'])

    # =========================================================================
    # BONUS POLICIES
    # =========================================================================
    op.create_table(
        'bonus_policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('score_bands', sa.JSON(), nullable=True),  # [{min: 0, max: 50, factor: 0}, {min: 50, max: 80, factor: 0.5}, ...]
        sa.Column('applicable_period_types', sa.JSON(), nullable=True),  # ['annual', 'semi_annual']
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('ix_bonus_policies_code', 'bonus_policies', ['code'], unique=True)

    # =========================================================================
    # PERFORMANCE SNAPSHOTS (denormalized for analytics)
    # =========================================================================
    op.create_table(
        'performance_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('evaluation_period_id', sa.Integer(), sa.ForeignKey('evaluation_periods.id'), nullable=False),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('final_score', sa.Numeric(8, 4), nullable=True),
        sa.Column('final_rating', sa.String(50), nullable=True),
        sa.Column('kra_scores', sa.JSON(), nullable=True),  # {kra_code: score, ...}
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
    )
    op.create_index('ix_snapshots_employee_id', 'performance_snapshots', ['employee_id'])
    op.create_index('ix_snapshots_period_id', 'performance_snapshots', ['evaluation_period_id'])
    op.create_index('ix_snapshots_department_id', 'performance_snapshots', ['department_id'])
    op.create_index('ix_snapshot_employee_period', 'performance_snapshots', ['employee_id', 'evaluation_period_id'])
    op.create_index('ix_snapshot_period_department', 'performance_snapshots', ['evaluation_period_id', 'department_id'])

    # =========================================================================
    # SEED DATA - Common KRAs
    # =========================================================================
    kra_table = sa.table(
        'kra_definitions',
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('description', sa.Text),
        sa.column('category', sa.String),
        sa.column('is_active', sa.Boolean),
    )
    op.bulk_insert(kra_table, [
        {'code': 'KRA_PRODUCTIVITY', 'name': 'Productivity & Output', 'description': 'Measures volume and efficiency of work completed', 'category': 'Operations', 'is_active': True},
        {'code': 'KRA_QUALITY', 'name': 'Quality & Accuracy', 'description': 'Measures accuracy, error rates, and quality of deliverables', 'category': 'Operations', 'is_active': True},
        {'code': 'KRA_CUSTOMER', 'name': 'Customer Satisfaction', 'description': 'Measures customer feedback, satisfaction scores, and service quality', 'category': 'Customer', 'is_active': True},
        {'code': 'KRA_TIMELINESS', 'name': 'Timeliness & SLA', 'description': 'Measures adherence to deadlines and SLA compliance', 'category': 'Operations', 'is_active': True},
        {'code': 'KRA_TEAMWORK', 'name': 'Collaboration & Teamwork', 'description': 'Measures cross-functional collaboration and team contribution', 'category': 'Behavior', 'is_active': True},
    ])

    # =========================================================================
    # SEED DATA - Ticketing KPIs
    # =========================================================================
    kpi_table = sa.table(
        'kpi_definitions',
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('description', sa.Text),
        sa.column('data_source', sa.String),
        sa.column('aggregation', sa.String),
        sa.column('query_config', sa.JSON),
        sa.column('scoring_method', sa.String),
        sa.column('min_value', sa.Numeric),
        sa.column('target_value', sa.Numeric),
        sa.column('max_value', sa.Numeric),
        sa.column('higher_is_better', sa.Boolean),
    )
    op.bulk_insert(kpi_table, [
        # Ticketing KPIs
        {
            'code': 'TKT_RESOLVED',
            'name': 'Tickets Resolved',
            'description': 'Total number of tickets resolved in the period',
            'data_source': 'ticketing',
            'aggregation': 'count',
            'query_config': {'table': 'tickets', 'filter': {'status': 'closed'}},
            'scoring_method': 'linear',
            'min_value': 0, 'target_value': 50, 'max_value': 100,
            'higher_is_better': True,
        },
        {
            'code': 'TKT_SLA_PCT',
            'name': 'SLA Compliance Rate',
            'description': 'Percentage of tickets resolved within SLA',
            'data_source': 'ticketing',
            'aggregation': 'percent',
            'query_config': {'table': 'tickets', 'numerator': {'sla_met': True}, 'denominator': {'status': 'closed'}},
            'scoring_method': 'threshold',
            'min_value': 0, 'target_value': 95, 'max_value': 100,
            'higher_is_better': True,
        },
        {
            'code': 'TKT_AVG_RESOLUTION',
            'name': 'Avg Resolution Time (hrs)',
            'description': 'Average time to resolve tickets in hours',
            'data_source': 'ticketing',
            'aggregation': 'avg',
            'query_config': {'table': 'tickets', 'field': 'resolution_time_hours'},
            'scoring_method': 'linear',
            'min_value': 72, 'target_value': 24, 'max_value': 4,
            'higher_is_better': False,
        },
        {
            'code': 'TKT_REOPEN_RATE',
            'name': 'Ticket Reopen Rate',
            'description': 'Percentage of resolved tickets that were reopened',
            'data_source': 'ticketing',
            'aggregation': 'percent',
            'query_config': {'table': 'tickets', 'numerator': {'reopened': True}, 'denominator': {'status': 'closed'}},
            'scoring_method': 'threshold',
            'min_value': 20, 'target_value': 5, 'max_value': 0,
            'higher_is_better': False,
        },
        {
            'code': 'TKT_CSAT',
            'name': 'Customer Satisfaction Score',
            'description': 'Average customer satisfaction rating (1-5 scale)',
            'data_source': 'ticketing',
            'aggregation': 'avg',
            'query_config': {'table': 'tickets', 'field': 'csat_score'},
            'scoring_method': 'linear',
            'min_value': 1, 'target_value': 4.5, 'max_value': 5,
            'higher_is_better': True,
        },
        {
            'code': 'TKT_FIRST_RESPONSE',
            'name': 'Avg First Response Time (mins)',
            'description': 'Average time to first response in minutes',
            'data_source': 'ticketing',
            'aggregation': 'avg',
            'query_config': {'table': 'tickets', 'field': 'first_response_minutes'},
            'scoring_method': 'linear',
            'min_value': 120, 'target_value': 30, 'max_value': 5,
            'higher_is_better': False,
        },
        # Field Service KPIs
        {
            'code': 'FS_COMPLETED',
            'name': 'Work Orders Completed',
            'description': 'Total number of service orders completed',
            'data_source': 'field_service',
            'aggregation': 'count',
            'query_config': {'table': 'service_orders', 'filter': {'status': 'completed'}},
            'scoring_method': 'linear',
            'min_value': 0, 'target_value': 30, 'max_value': 60,
            'higher_is_better': True,
        },
        {
            'code': 'FS_FIRST_FIX',
            'name': 'First-Time Fix Rate',
            'description': 'Percentage of jobs resolved on first visit',
            'data_source': 'field_service',
            'aggregation': 'percent',
            'query_config': {'table': 'service_orders', 'numerator': {'first_time_fix': True}, 'denominator': {'status': 'completed'}},
            'scoring_method': 'threshold',
            'min_value': 0, 'target_value': 85, 'max_value': 100,
            'higher_is_better': True,
        },
        {
            'code': 'FS_ON_TIME',
            'name': 'On-Time Arrival Rate',
            'description': 'Percentage of jobs with on-time arrival within scheduled window',
            'data_source': 'field_service',
            'aggregation': 'percent',
            'query_config': {'table': 'service_orders', 'numerator': {'arrived_on_time': True}, 'denominator': {'status': 'completed'}},
            'scoring_method': 'threshold',
            'min_value': 0, 'target_value': 90, 'max_value': 100,
            'higher_is_better': True,
        },
        {
            'code': 'FS_AVG_DURATION',
            'name': 'Avg Job Duration (mins)',
            'description': 'Average time spent on each service order',
            'data_source': 'field_service',
            'aggregation': 'avg',
            'query_config': {'table': 'service_orders', 'field': 'job_duration_minutes'},
            'scoring_method': 'band',
            'min_value': 180, 'target_value': 60, 'max_value': 30,
            'higher_is_better': False,
        },
        {
            'code': 'FS_CUSTOMER_RATING',
            'name': 'Customer Rating',
            'description': 'Average customer rating for field service visits',
            'data_source': 'field_service',
            'aggregation': 'avg',
            'query_config': {'table': 'service_orders', 'field': 'customer_rating'},
            'scoring_method': 'linear',
            'min_value': 1, 'target_value': 4.5, 'max_value': 5,
            'higher_is_better': True,
        },
        {
            'code': 'FS_PM_COMPLETION',
            'name': 'Preventive Maintenance Completion',
            'description': 'Percentage of scheduled preventive maintenance jobs completed',
            'data_source': 'field_service',
            'aggregation': 'percent',
            'query_config': {'table': 'service_orders', 'filter': {'order_type': 'preventive'}, 'numerator': {'status': 'completed'}, 'denominator': {}},
            'scoring_method': 'threshold',
            'min_value': 0, 'target_value': 95, 'max_value': 100,
            'higher_is_better': True,
        },
    ])

    # =========================================================================
    # SEED DATA - Default Bonus Policy
    # =========================================================================
    bonus_table = sa.table(
        'bonus_policies',
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('score_bands', sa.JSON),
        sa.column('applicable_period_types', sa.JSON),
        sa.column('is_active', sa.Boolean),
    )
    op.bulk_insert(bonus_table, [
        {
            'code': 'STANDARD_BONUS',
            'name': 'Standard Performance Bonus',
            'score_bands': [
                {'min': 0, 'max': 50, 'factor': 0, 'label': 'Below Expectations'},
                {'min': 50, 'max': 70, 'factor': 0.5, 'label': 'Meets Expectations'},
                {'min': 70, 'max': 85, 'factor': 1.0, 'label': 'Exceeds Expectations'},
                {'min': 85, 'max': 100, 'factor': 1.5, 'label': 'Outstanding'},
            ],
            'applicable_period_types': ['annual', 'semi_annual'],
            'is_active': True,
        },
    ])


def downgrade() -> None:
    # Drop tables in reverse order (respect FK constraints)
    op.drop_index('ix_snapshot_period_department', table_name='performance_snapshots')
    op.drop_index('ix_snapshot_employee_period', table_name='performance_snapshots')
    op.drop_index('ix_snapshots_department_id', table_name='performance_snapshots')
    op.drop_index('ix_snapshots_period_id', table_name='performance_snapshots')
    op.drop_index('ix_snapshots_employee_id', table_name='performance_snapshots')
    op.drop_table('performance_snapshots')

    op.drop_index('ix_bonus_policies_code', table_name='bonus_policies')
    op.drop_table('bonus_policies')

    op.drop_index('ix_review_notes_kra_result_id', table_name='performance_review_notes')
    op.drop_index('ix_review_notes_kpi_result_id', table_name='performance_review_notes')
    op.drop_index('ix_review_notes_scorecard_id', table_name='performance_review_notes')
    op.drop_table('performance_review_notes')

    op.drop_index('ix_score_overrides_kra_result_id', table_name='score_overrides')
    op.drop_index('ix_score_overrides_kpi_result_id', table_name='score_overrides')
    op.drop_index('ix_score_overrides_scorecard_id', table_name='score_overrides')
    op.drop_table('score_overrides')

    op.drop_index('ix_kra_results_kra_id', table_name='kra_results')
    op.drop_index('ix_kra_results_scorecard_id', table_name='kra_results')
    op.drop_table('kra_results')

    op.drop_index('ix_kpi_results_kra_id', table_name='kpi_results')
    op.drop_index('ix_kpi_results_kpi_id', table_name='kpi_results')
    op.drop_index('ix_kpi_results_scorecard_id', table_name='kpi_results')
    op.drop_table('kpi_results')

    op.drop_index('ix_scorecard_employee_period', table_name='employee_scorecard_instances')
    op.drop_index('ix_scorecard_instances_status', table_name='employee_scorecard_instances')
    op.drop_index('ix_scorecard_instances_template_id', table_name='employee_scorecard_instances')
    op.drop_index('ix_scorecard_instances_period_id', table_name='employee_scorecard_instances')
    op.drop_index('ix_scorecard_instances_employee_id', table_name='employee_scorecard_instances')
    op.drop_table('employee_scorecard_instances')

    op.drop_index('ix_kpi_bindings_kpi_department', table_name='kpi_bindings')
    op.drop_index('ix_kpi_bindings_kpi_employee', table_name='kpi_bindings')
    op.drop_index('ix_kpi_bindings_department_id', table_name='kpi_bindings')
    op.drop_index('ix_kpi_bindings_employee_id', table_name='kpi_bindings')
    op.drop_index('ix_kpi_bindings_kpi_id', table_name='kpi_bindings')
    op.drop_table('kpi_bindings')

    op.drop_index('ix_template_kra_unique', table_name='scorecard_template_items')
    op.drop_index('ix_scorecard_template_items_kra_id', table_name='scorecard_template_items')
    op.drop_index('ix_scorecard_template_items_template_id', table_name='scorecard_template_items')
    op.drop_table('scorecard_template_items')

    op.drop_index('ix_scorecard_templates_is_active', table_name='scorecard_templates')
    op.drop_index('ix_scorecard_templates_code', table_name='scorecard_templates')
    op.drop_table('scorecard_templates')

    op.drop_index('ix_kra_kpi_unique', table_name='kra_kpi_map')
    op.drop_index('ix_kra_kpi_map_kpi_id', table_name='kra_kpi_map')
    op.drop_index('ix_kra_kpi_map_kra_id', table_name='kra_kpi_map')
    op.drop_table('kra_kpi_map')

    op.drop_index('ix_kpi_definitions_data_source', table_name='kpi_definitions')
    op.drop_index('ix_kpi_definitions_code', table_name='kpi_definitions')
    op.drop_table('kpi_definitions')

    op.drop_index('ix_kra_definitions_category', table_name='kra_definitions')
    op.drop_index('ix_kra_definitions_code', table_name='kra_definitions')
    op.drop_table('kra_definitions')

    op.drop_index('ix_evaluation_periods_start_date', table_name='evaluation_periods')
    op.drop_index('ix_evaluation_periods_status', table_name='evaluation_periods')
    op.drop_index('ix_evaluation_periods_code', table_name='evaluation_periods')
    op.drop_table('evaluation_periods')
