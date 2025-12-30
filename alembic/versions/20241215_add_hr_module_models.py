"""Add HR Module models - Full HR sync support

Revision ID: 20241215_hr_module
Revises: 20240920_add_agents_and_teams
Create Date: 2024-12-15

This migration adds all HR module tables:
- Reference Data: employee_grades, employee_groups, employee_group_members
- Leave Management: leave_types, holiday_lists, holidays, leave_policies,
                    leave_policy_details, leave_allocations, leave_applications
- Attendance: shift_types, shift_assignments, attendances, attendance_requests
- Payroll: salary_components, salary_structures, salary_structure_earnings,
           salary_structure_deductions, salary_structure_assignments,
           payroll_entries, salary_slips, salary_slip_earnings, salary_slip_deductions
- Recruitment: job_openings, job_applicants, job_offers, job_offer_terms
- Training: training_programs, training_events, training_event_employees, training_results
- Appraisal: appraisal_templates, appraisal_template_goals, appraisals, appraisal_goals
- Lifecycle: employee_onboardings, employee_onboarding_activities,
             employee_separations, employee_separation_activities,
             employee_promotions, employee_promotion_details,
             employee_transfers, employee_transfer_details
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20241215_hr_module'
down_revision = '20240920_add_agents_and_teams'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==================== REFERENCE DATA ====================

    # Employee Grades
    op.create_table(
        'employee_grades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('grade_name', sa.String(255), nullable=False, unique=True),
        sa.Column('default_leave_policy', sa.String(255), nullable=True),
        sa.Column('default_salary_structure', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_employee_grades_erpnext_id', 'employee_grades', ['erpnext_id'], unique=True)

    # Employee Groups
    op.create_table(
        'employee_groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee_group_name', sa.String(255), nullable=False, unique=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_employee_groups_erpnext_id', 'employee_groups', ['erpnext_id'], unique=True)

    # Employee Group Members (child table)
    op.create_table(
        'employee_group_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('employee_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_employee_group_members_group_id', 'employee_group_members', ['group_id'])
    op.create_index('ix_employee_group_members_employee_id', 'employee_group_members', ['employee_id'])

    # ==================== LEAVE MANAGEMENT ====================

    # Leave Types
    op.create_table(
        'leave_types',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('leave_type_name', sa.String(255), nullable=False, unique=True),
        sa.Column('max_leaves_allowed', sa.Integer(), default=0),
        sa.Column('max_continuous_days_allowed', sa.Integer(), nullable=True),
        sa.Column('is_carry_forward', sa.Boolean(), default=False),
        sa.Column('is_lwp', sa.Boolean(), default=False),
        sa.Column('is_optional_leave', sa.Boolean(), default=False),
        sa.Column('is_compensatory', sa.Boolean(), default=False),
        sa.Column('allow_encashment', sa.Boolean(), default=False),
        sa.Column('include_holiday', sa.Boolean(), default=False),
        sa.Column('is_earned_leave', sa.Boolean(), default=False),
        sa.Column('earned_leave_frequency', sa.String(50), nullable=True),
        sa.Column('rounding', sa.Numeric(), default=0.5),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_leave_types_erpnext_id', 'leave_types', ['erpnext_id'], unique=True)

    # Holiday Lists
    op.create_table(
        'holiday_lists',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('holiday_list_name', sa.String(255), nullable=False),
        sa.Column('from_date', sa.Date(), nullable=True),
        sa.Column('to_date', sa.Date(), nullable=True),
        sa.Column('total_holidays', sa.Integer(), default=0),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('weekly_off', sa.String(50), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_holiday_lists_erpnext_id', 'holiday_lists', ['erpnext_id'], unique=True)
    op.create_index('ix_holiday_lists_name', 'holiday_lists', ['holiday_list_name'])

    # Holidays (child table)
    op.create_table(
        'holidays',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('holiday_list_id', sa.Integer(), sa.ForeignKey('holiday_lists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('holiday_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('weekly_off', sa.Boolean(), default=False),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_holidays_holiday_list_id', 'holidays', ['holiday_list_id'])
    op.create_index('ix_holidays_holiday_date', 'holidays', ['holiday_date'])
    op.create_index('ix_holidays_list_date', 'holidays', ['holiday_list_id', 'holiday_date'])

    # Leave Policies
    op.create_table(
        'leave_policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('leave_policy_name', sa.String(255), nullable=False, unique=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_leave_policies_erpnext_id', 'leave_policies', ['erpnext_id'], unique=True)

    # Leave Policy Details (child table)
    op.create_table(
        'leave_policy_details',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('leave_policy_id', sa.Integer(), sa.ForeignKey('leave_policies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('leave_type', sa.String(255), nullable=False),
        sa.Column('leave_type_id', sa.Integer(), sa.ForeignKey('leave_types.id'), nullable=True),
        sa.Column('annual_allocation', sa.Numeric(), default=0),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_leave_policy_details_policy_id', 'leave_policy_details', ['leave_policy_id'])

    # Leave Allocations
    op.create_table(
        'leave_allocations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('leave_type', sa.String(255), nullable=False),
        sa.Column('leave_type_id', sa.Integer(), sa.ForeignKey('leave_types.id'), nullable=True),
        sa.Column('from_date', sa.Date(), nullable=False),
        sa.Column('to_date', sa.Date(), nullable=False),
        sa.Column('new_leaves_allocated', sa.Numeric(), default=0),
        sa.Column('total_leaves_allocated', sa.Numeric(), default=0),
        sa.Column('unused_leaves', sa.Numeric(), default=0),
        sa.Column('carry_forwarded_leaves', sa.Numeric(), default=0),
        sa.Column('carry_forwarded_leaves_count', sa.Numeric(), default=0),
        sa.Column('leave_policy', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), default='draft'),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_leave_allocations_erpnext_id', 'leave_allocations', ['erpnext_id'], unique=True)
    op.create_index('ix_leave_allocations_employee', 'leave_allocations', ['employee'])
    op.create_index('ix_leave_allocations_employee_id', 'leave_allocations', ['employee_id'])
    op.create_index('ix_leave_allocations_leave_type', 'leave_allocations', ['leave_type'])
    op.create_index('ix_leave_allocations_from_date', 'leave_allocations', ['from_date'])

    # Leave Applications
    op.create_table(
        'leave_applications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('leave_type', sa.String(255), nullable=False),
        sa.Column('leave_type_id', sa.Integer(), sa.ForeignKey('leave_types.id'), nullable=True),
        sa.Column('from_date', sa.Date(), nullable=False),
        sa.Column('to_date', sa.Date(), nullable=False),
        sa.Column('half_day', sa.Boolean(), default=False),
        sa.Column('half_day_date', sa.Date(), nullable=True),
        sa.Column('total_leave_days', sa.Numeric(), default=0),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('leave_approver', sa.String(255), nullable=True),
        sa.Column('leave_approver_name', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), default='open'),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('posting_date', sa.Date(), nullable=False),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_leave_applications_erpnext_id', 'leave_applications', ['erpnext_id'], unique=True)
    op.create_index('ix_leave_applications_employee', 'leave_applications', ['employee'])
    op.create_index('ix_leave_applications_employee_id', 'leave_applications', ['employee_id'])
    op.create_index('ix_leave_applications_status', 'leave_applications', ['status'])
    op.create_index('ix_leave_applications_from_date', 'leave_applications', ['from_date'])

    # ==================== ATTENDANCE ====================

    # Shift Types
    op.create_table(
        'shift_types',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('shift_type_name', sa.String(255), nullable=False, unique=True),
        sa.Column('start_time', sa.Time(), nullable=True),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('working_hours_threshold_for_half_day', sa.Numeric(), default=0),
        sa.Column('working_hours_threshold_for_absent', sa.Numeric(), default=0),
        sa.Column('determine_check_in_and_check_out', sa.String(100), nullable=True),
        sa.Column('begin_check_in_before_shift_start_time', sa.Integer(), default=0),
        sa.Column('allow_check_out_after_shift_end_time', sa.Integer(), default=0),
        sa.Column('enable_auto_attendance', sa.Boolean(), default=False),
        sa.Column('enable_entry_grace_period', sa.Boolean(), default=False),
        sa.Column('late_entry_grace_period', sa.Integer(), default=0),
        sa.Column('enable_exit_grace_period', sa.Boolean(), default=False),
        sa.Column('early_exit_grace_period', sa.Integer(), default=0),
        sa.Column('holiday_list', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_shift_types_erpnext_id', 'shift_types', ['erpnext_id'], unique=True)

    # Shift Assignments
    op.create_table(
        'shift_assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('shift_type', sa.String(255), nullable=False),
        sa.Column('shift_type_id', sa.Integer(), sa.ForeignKey('shift_types.id'), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_shift_assignments_erpnext_id', 'shift_assignments', ['erpnext_id'], unique=True)
    op.create_index('ix_shift_assignments_employee', 'shift_assignments', ['employee'])
    op.create_index('ix_shift_assignments_employee_id', 'shift_assignments', ['employee_id'])
    op.create_index('ix_shift_assignments_start_date', 'shift_assignments', ['start_date'])

    # Attendances
    op.create_table(
        'attendances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('attendance_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), default='present'),
        sa.Column('leave_type', sa.String(255), nullable=True),
        sa.Column('leave_application', sa.String(255), nullable=True),
        sa.Column('shift', sa.String(255), nullable=True),
        sa.Column('in_time', sa.DateTime(), nullable=True),
        sa.Column('out_time', sa.DateTime(), nullable=True),
        sa.Column('working_hours', sa.Numeric(), default=0),
        sa.Column('late_entry', sa.Boolean(), default=False),
        sa.Column('early_exit', sa.Boolean(), default=False),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_attendances_erpnext_id', 'attendances', ['erpnext_id'], unique=True)
    op.create_index('ix_attendances_employee', 'attendances', ['employee'])
    op.create_index('ix_attendances_employee_id', 'attendances', ['employee_id'])
    op.create_index('ix_attendances_date', 'attendances', ['attendance_date'])
    op.create_index('ix_attendances_status', 'attendances', ['status'])
    op.create_index('ix_attendances_emp_date', 'attendances', ['employee_id', 'attendance_date'], unique=True)

    # Attendance Requests
    op.create_table(
        'attendance_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('from_date', sa.Date(), nullable=False),
        sa.Column('to_date', sa.Date(), nullable=False),
        sa.Column('half_day', sa.Boolean(), default=False),
        sa.Column('half_day_date', sa.Date(), nullable=True),
        sa.Column('reason', sa.String(255), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), default='draft'),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_attendance_requests_erpnext_id', 'attendance_requests', ['erpnext_id'], unique=True)
    op.create_index('ix_attendance_requests_employee', 'attendance_requests', ['employee'])
    op.create_index('ix_attendance_requests_employee_id', 'attendance_requests', ['employee_id'])
    op.create_index('ix_attendance_requests_status', 'attendance_requests', ['status'])

    # ==================== PAYROLL ====================

    # Salary Components
    op.create_table(
        'salary_components',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('salary_component_name', sa.String(255), nullable=False, unique=True),
        sa.Column('salary_component_abbr', sa.String(50), nullable=True),
        sa.Column('type', sa.String(50), default='earning'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_tax_applicable', sa.Boolean(), default=False),
        sa.Column('is_payable', sa.Boolean(), default=True),
        sa.Column('is_flexible_benefit', sa.Boolean(), default=False),
        sa.Column('depends_on_payment_days', sa.Boolean(), default=True),
        sa.Column('variable_based_on_taxable_salary', sa.Boolean(), default=False),
        sa.Column('exempted_from_income_tax', sa.Boolean(), default=False),
        sa.Column('statistical_component', sa.Boolean(), default=False),
        sa.Column('do_not_include_in_total', sa.Boolean(), default=False),
        sa.Column('disabled', sa.Boolean(), default=False),
        sa.Column('default_account', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_salary_components_erpnext_id', 'salary_components', ['erpnext_id'], unique=True)
    op.create_index('ix_salary_components_type', 'salary_components', ['type'])

    # Salary Structures
    op.create_table(
        'salary_structures',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('salary_structure_name', sa.String(255), nullable=False),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('is_active', sa.String(10), default='Yes'),
        sa.Column('payroll_frequency', sa.String(50), nullable=True),
        sa.Column('currency', sa.String(10), default='USD'),
        sa.Column('payment_account', sa.String(255), nullable=True),
        sa.Column('mode_of_payment', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_salary_structures_erpnext_id', 'salary_structures', ['erpnext_id'], unique=True)
    op.create_index('ix_salary_structures_name', 'salary_structures', ['salary_structure_name'])

    # Salary Structure Earnings (child table)
    op.create_table(
        'salary_structure_earnings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('salary_structure_id', sa.Integer(), sa.ForeignKey('salary_structures.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('salary_component', sa.String(255), nullable=False),
        sa.Column('abbr', sa.String(50), nullable=True),
        sa.Column('amount', sa.Numeric(), default=0),
        sa.Column('amount_based_on_formula', sa.Boolean(), default=False),
        sa.Column('formula', sa.Text(), nullable=True),
        sa.Column('condition', sa.Text(), nullable=True),
        sa.Column('statistical_component', sa.Boolean(), default=False),
        sa.Column('do_not_include_in_total', sa.Boolean(), default=False),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_salary_structure_earnings_struct_id', 'salary_structure_earnings', ['salary_structure_id'])

    # Salary Structure Deductions (child table)
    op.create_table(
        'salary_structure_deductions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('salary_structure_id', sa.Integer(), sa.ForeignKey('salary_structures.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('salary_component', sa.String(255), nullable=False),
        sa.Column('abbr', sa.String(50), nullable=True),
        sa.Column('amount', sa.Numeric(), default=0),
        sa.Column('amount_based_on_formula', sa.Boolean(), default=False),
        sa.Column('formula', sa.Text(), nullable=True),
        sa.Column('condition', sa.Text(), nullable=True),
        sa.Column('statistical_component', sa.Boolean(), default=False),
        sa.Column('do_not_include_in_total', sa.Boolean(), default=False),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_salary_structure_deductions_struct_id', 'salary_structure_deductions', ['salary_structure_id'])

    # Salary Structure Assignments
    op.create_table(
        'salary_structure_assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('salary_structure', sa.String(255), nullable=False),
        sa.Column('salary_structure_id', sa.Integer(), sa.ForeignKey('salary_structures.id'), nullable=True),
        sa.Column('from_date', sa.Date(), nullable=False),
        sa.Column('base', sa.Numeric(), default=0),
        sa.Column('variable', sa.Numeric(), default=0),
        sa.Column('income_tax_slab', sa.String(255), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_salary_struct_assignments_erpnext_id', 'salary_structure_assignments', ['erpnext_id'], unique=True)
    op.create_index('ix_salary_struct_assignments_employee', 'salary_structure_assignments', ['employee'])
    op.create_index('ix_salary_struct_assignments_employee_id', 'salary_structure_assignments', ['employee_id'])

    # Payroll Entries
    op.create_table(
        'payroll_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('posting_date', sa.Date(), nullable=False),
        sa.Column('payroll_frequency', sa.String(50), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('branch', sa.String(255), nullable=True),
        sa.Column('designation', sa.String(255), nullable=True),
        sa.Column('currency', sa.String(10), default='USD'),
        sa.Column('exchange_rate', sa.Numeric(), default=1),
        sa.Column('payment_account', sa.String(255), nullable=True),
        sa.Column('bank_account', sa.String(255), nullable=True),
        sa.Column('salary_slips_created', sa.Boolean(), default=False),
        sa.Column('salary_slips_submitted', sa.Boolean(), default=False),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_payroll_entries_erpnext_id', 'payroll_entries', ['erpnext_id'], unique=True)
    op.create_index('ix_payroll_entries_posting_date', 'payroll_entries', ['posting_date'])
    op.create_index('ix_payroll_entries_period', 'payroll_entries', ['start_date', 'end_date'])

    # Salary Slips
    op.create_table(
        'salary_slips',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('designation', sa.String(255), nullable=True),
        sa.Column('branch', sa.String(255), nullable=True),
        sa.Column('salary_structure', sa.String(255), nullable=True),
        sa.Column('posting_date', sa.Date(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('payroll_frequency', sa.String(50), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('currency', sa.String(10), default='USD'),
        sa.Column('total_working_days', sa.Numeric(), default=0),
        sa.Column('absent_days', sa.Numeric(), default=0),
        sa.Column('payment_days', sa.Numeric(), default=0),
        sa.Column('leave_without_pay', sa.Numeric(), default=0),
        sa.Column('gross_pay', sa.Numeric(), default=0),
        sa.Column('total_deduction', sa.Numeric(), default=0),
        sa.Column('net_pay', sa.Numeric(), default=0),
        sa.Column('rounded_total', sa.Numeric(), default=0),
        sa.Column('status', sa.String(50), default='draft'),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('bank_name', sa.String(255), nullable=True),
        sa.Column('bank_account_no', sa.String(100), nullable=True),
        sa.Column('payroll_entry', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_salary_slips_erpnext_id', 'salary_slips', ['erpnext_id'], unique=True)
    op.create_index('ix_salary_slips_employee', 'salary_slips', ['employee'])
    op.create_index('ix_salary_slips_employee_id', 'salary_slips', ['employee_id'])
    op.create_index('ix_salary_slips_posting_date', 'salary_slips', ['posting_date'])
    op.create_index('ix_salary_slips_status', 'salary_slips', ['status'])
    op.create_index('ix_salary_slips_emp_period', 'salary_slips', ['employee_id', 'start_date', 'end_date'])

    # Salary Slip Earnings (child table)
    op.create_table(
        'salary_slip_earnings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('salary_slip_id', sa.Integer(), sa.ForeignKey('salary_slips.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('salary_component', sa.String(255), nullable=False),
        sa.Column('abbr', sa.String(50), nullable=True),
        sa.Column('amount', sa.Numeric(), default=0),
        sa.Column('default_amount', sa.Numeric(), default=0),
        sa.Column('additional_amount', sa.Numeric(), default=0),
        sa.Column('year_to_date', sa.Numeric(), default=0),
        sa.Column('statistical_component', sa.Boolean(), default=False),
        sa.Column('do_not_include_in_total', sa.Boolean(), default=False),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_salary_slip_earnings_slip_id', 'salary_slip_earnings', ['salary_slip_id'])

    # Salary Slip Deductions (child table)
    op.create_table(
        'salary_slip_deductions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('salary_slip_id', sa.Integer(), sa.ForeignKey('salary_slips.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('salary_component', sa.String(255), nullable=False),
        sa.Column('abbr', sa.String(50), nullable=True),
        sa.Column('amount', sa.Numeric(), default=0),
        sa.Column('default_amount', sa.Numeric(), default=0),
        sa.Column('additional_amount', sa.Numeric(), default=0),
        sa.Column('year_to_date', sa.Numeric(), default=0),
        sa.Column('statistical_component', sa.Boolean(), default=False),
        sa.Column('do_not_include_in_total', sa.Boolean(), default=False),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_salary_slip_deductions_slip_id', 'salary_slip_deductions', ['salary_slip_id'])

    # ==================== RECRUITMENT ====================

    # Job Openings
    op.create_table(
        'job_openings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('job_title', sa.String(500), nullable=False),
        sa.Column('designation', sa.String(255), nullable=True),
        sa.Column('designation_id', sa.Integer(), sa.ForeignKey('designations.id'), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), default='open'),
        sa.Column('publish', sa.Boolean(), default=False),
        sa.Column('route', sa.String(500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('lower_range', sa.Numeric(), default=0),
        sa.Column('upper_range', sa.Numeric(), default=0),
        sa.Column('currency', sa.String(10), default='USD'),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_job_openings_erpnext_id', 'job_openings', ['erpnext_id'], unique=True)
    op.create_index('ix_job_openings_job_title', 'job_openings', ['job_title'])
    op.create_index('ix_job_openings_status', 'job_openings', ['status'])

    # Job Applicants
    op.create_table(
        'job_applicants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('applicant_name', sa.String(255), nullable=False),
        sa.Column('email_id', sa.String(255), nullable=True),
        sa.Column('phone_number', sa.String(50), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('job_title', sa.String(500), nullable=True),
        sa.Column('job_opening', sa.String(255), nullable=True),
        sa.Column('job_opening_id', sa.Integer(), sa.ForeignKey('job_openings.id'), nullable=True),
        sa.Column('status', sa.String(50), default='open'),
        sa.Column('cover_letter', sa.Text(), nullable=True),
        sa.Column('resume_attachment', sa.String(500), nullable=True),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('source_name', sa.String(255), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_job_applicants_erpnext_id', 'job_applicants', ['erpnext_id'], unique=True)
    op.create_index('ix_job_applicants_name', 'job_applicants', ['applicant_name'])
    op.create_index('ix_job_applicants_email', 'job_applicants', ['email_id'])
    op.create_index('ix_job_applicants_status', 'job_applicants', ['status'])

    # Job Offers
    op.create_table(
        'job_offers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('job_applicant', sa.String(255), nullable=False),
        sa.Column('job_applicant_id', sa.Integer(), sa.ForeignKey('job_applicants.id'), nullable=True),
        sa.Column('applicant_name', sa.String(255), nullable=True),
        sa.Column('applicant_email', sa.String(255), nullable=True),
        sa.Column('designation', sa.String(255), nullable=True),
        sa.Column('offer_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('base', sa.Numeric(), default=0),
        sa.Column('salary_structure', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_job_offers_erpnext_id', 'job_offers', ['erpnext_id'], unique=True)
    op.create_index('ix_job_offers_applicant', 'job_offers', ['job_applicant'])
    op.create_index('ix_job_offers_status', 'job_offers', ['status'])
    op.create_index('ix_job_offers_date', 'job_offers', ['offer_date'])

    # Job Offer Terms (child table)
    op.create_table(
        'job_offer_terms',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_offer_id', sa.Integer(), sa.ForeignKey('job_offers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('offer_term', sa.String(255), nullable=True),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_job_offer_terms_offer_id', 'job_offer_terms', ['job_offer_id'])

    # ==================== TRAINING ====================

    # Training Programs
    op.create_table(
        'training_programs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('training_program_name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trainer_name', sa.String(255), nullable=True),
        sa.Column('trainer_email', sa.String(255), nullable=True),
        sa.Column('supplier', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_training_programs_erpnext_id', 'training_programs', ['erpnext_id'], unique=True)

    # Training Events
    op.create_table(
        'training_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('event_name', sa.String(500), nullable=False),
        sa.Column('training_program', sa.String(255), nullable=True),
        sa.Column('training_program_id', sa.Integer(), sa.ForeignKey('training_programs.id'), nullable=True),
        sa.Column('type', sa.String(100), nullable=True),
        sa.Column('level', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), default='scheduled'),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('location', sa.String(500), nullable=True),
        sa.Column('trainer_name', sa.String(255), nullable=True),
        sa.Column('trainer_email', sa.String(255), nullable=True),
        sa.Column('course', sa.String(255), nullable=True),
        sa.Column('introduction', sa.Text(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_training_events_erpnext_id', 'training_events', ['erpnext_id'], unique=True)
    op.create_index('ix_training_events_name', 'training_events', ['event_name'])
    op.create_index('ix_training_events_status', 'training_events', ['status'])
    op.create_index('ix_training_events_start_time', 'training_events', ['start_time'])

    # Training Event Employees (child table)
    op.create_table(
        'training_event_employees',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('training_event_id', sa.Integer(), sa.ForeignKey('training_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('attendance', sa.String(50), nullable=True),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_training_event_employees_event_id', 'training_event_employees', ['training_event_id'])
    op.create_index('ix_training_event_employees_employee_id', 'training_event_employees', ['employee_id'])

    # Training Results
    op.create_table(
        'training_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('training_event', sa.String(255), nullable=False),
        sa.Column('training_event_id', sa.Integer(), sa.ForeignKey('training_events.id'), nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('hours', sa.Numeric(), default=0),
        sa.Column('grade', sa.String(20), nullable=True),
        sa.Column('result', sa.String(50), default='pending'),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_training_results_erpnext_id', 'training_results', ['erpnext_id'], unique=True)
    op.create_index('ix_training_results_event', 'training_results', ['training_event'])
    op.create_index('ix_training_results_employee', 'training_results', ['employee'])
    op.create_index('ix_training_results_result', 'training_results', ['result'])

    # ==================== APPRAISAL ====================

    # Appraisal Templates
    op.create_table(
        'appraisal_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('template_name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_appraisal_templates_erpnext_id', 'appraisal_templates', ['erpnext_id'], unique=True)

    # Appraisal Template Goals (child table)
    op.create_table(
        'appraisal_template_goals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('appraisal_template_id', sa.Integer(), sa.ForeignKey('appraisal_templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('kra', sa.String(500), nullable=True),
        sa.Column('per_weightage', sa.Numeric(), default=0),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_appraisal_template_goals_template_id', 'appraisal_template_goals', ['appraisal_template_id'])

    # Appraisals
    op.create_table(
        'appraisals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('appraisal_template', sa.String(255), nullable=True),
        sa.Column('appraisal_template_id', sa.Integer(), sa.ForeignKey('appraisal_templates.id'), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), default='draft'),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('total_score', sa.Numeric(), default=0),
        sa.Column('self_score', sa.Numeric(), default=0),
        sa.Column('final_score', sa.Numeric(), default=0),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('reflections', sa.Text(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_appraisals_erpnext_id', 'appraisals', ['erpnext_id'], unique=True)
    op.create_index('ix_appraisals_employee', 'appraisals', ['employee'])
    op.create_index('ix_appraisals_employee_id', 'appraisals', ['employee_id'])
    op.create_index('ix_appraisals_status', 'appraisals', ['status'])
    op.create_index('ix_appraisals_start_date', 'appraisals', ['start_date'])

    # Appraisal Goals (child table)
    op.create_table(
        'appraisal_goals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('appraisal_id', sa.Integer(), sa.ForeignKey('appraisals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('kra', sa.String(500), nullable=True),
        sa.Column('per_weightage', sa.Numeric(), default=0),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('score_earned', sa.Numeric(), default=0),
        sa.Column('self_score', sa.Numeric(), default=0),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_appraisal_goals_appraisal_id', 'appraisal_goals', ['appraisal_id'])

    # ==================== LIFECYCLE ====================

    # Employee Onboardings
    op.create_table(
        'employee_onboardings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('job_applicant', sa.String(255), nullable=True),
        sa.Column('job_offer', sa.String(255), nullable=True),
        sa.Column('date_of_joining', sa.Date(), nullable=True),
        sa.Column('boarding_status', sa.String(50), default='pending'),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('designation', sa.String(255), nullable=True),
        sa.Column('employee_onboarding_template', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_employee_onboardings_erpnext_id', 'employee_onboardings', ['erpnext_id'], unique=True)
    op.create_index('ix_employee_onboardings_employee', 'employee_onboardings', ['employee'])
    op.create_index('ix_employee_onboardings_status', 'employee_onboardings', ['boarding_status'])

    # Employee Onboarding Activities (child table)
    op.create_table(
        'employee_onboarding_activities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_onboarding_id', sa.Integer(), sa.ForeignKey('employee_onboardings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('activity_name', sa.String(500), nullable=False),
        sa.Column('user', sa.String(255), nullable=True),
        sa.Column('role', sa.String(255), nullable=True),
        sa.Column('required_for_employee_creation', sa.Boolean(), default=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('completed_on', sa.Date(), nullable=True),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_employee_onboarding_activities_onboarding_id', 'employee_onboarding_activities', ['employee_onboarding_id'])

    # Employee Separations
    op.create_table(
        'employee_separations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('resignation_letter_date', sa.Date(), nullable=True),
        sa.Column('separation_date', sa.Date(), nullable=True),
        sa.Column('boarding_status', sa.String(50), default='pending'),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('designation', sa.String(255), nullable=True),
        sa.Column('reason_for_leaving', sa.Text(), nullable=True),
        sa.Column('exit_interview', sa.Text(), nullable=True),
        sa.Column('employee_separation_template', sa.String(255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_employee_separations_erpnext_id', 'employee_separations', ['erpnext_id'], unique=True)
    op.create_index('ix_employee_separations_employee', 'employee_separations', ['employee'])
    op.create_index('ix_employee_separations_status', 'employee_separations', ['boarding_status'])

    # Employee Separation Activities (child table)
    op.create_table(
        'employee_separation_activities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_separation_id', sa.Integer(), sa.ForeignKey('employee_separations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('activity_name', sa.String(500), nullable=False),
        sa.Column('user', sa.String(255), nullable=True),
        sa.Column('role', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('completed_on', sa.Date(), nullable=True),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_employee_separation_activities_separation_id', 'employee_separation_activities', ['employee_separation_id'])

    # Employee Promotions
    op.create_table(
        'employee_promotions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('promotion_date', sa.Date(), nullable=False),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_employee_promotions_erpnext_id', 'employee_promotions', ['erpnext_id'], unique=True)
    op.create_index('ix_employee_promotions_employee', 'employee_promotions', ['employee'])
    op.create_index('ix_employee_promotions_date', 'employee_promotions', ['promotion_date'])

    # Employee Promotion Details (child table)
    op.create_table(
        'employee_promotion_details',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_promotion_id', sa.Integer(), sa.ForeignKey('employee_promotions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('property', sa.String(100), nullable=False),
        sa.Column('current', sa.String(255), nullable=True),
        sa.Column('new', sa.String(255), nullable=True),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_employee_promotion_details_promotion_id', 'employee_promotion_details', ['employee_promotion_id'])

    # Employee Transfers
    op.create_table(
        'employee_transfers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, nullable=True),
        sa.Column('employee', sa.String(255), nullable=False),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('employee_name', sa.String(255), nullable=True),
        sa.Column('transfer_date', sa.Date(), nullable=False),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('new_company', sa.String(255), nullable=True),
        sa.Column('docstatus', sa.Integer(), default=0),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_employee_transfers_erpnext_id', 'employee_transfers', ['erpnext_id'], unique=True)
    op.create_index('ix_employee_transfers_employee', 'employee_transfers', ['employee'])
    op.create_index('ix_employee_transfers_date', 'employee_transfers', ['transfer_date'])

    # Employee Transfer Details (child table)
    op.create_table(
        'employee_transfer_details',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_transfer_id', sa.Integer(), sa.ForeignKey('employee_transfers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('erpnext_name', sa.String(255), nullable=True),
        sa.Column('property', sa.String(100), nullable=False),
        sa.Column('current', sa.String(255), nullable=True),
        sa.Column('new', sa.String(255), nullable=True),
        sa.Column('idx', sa.Integer(), default=0),
    )
    op.create_index('ix_employee_transfer_details_transfer_id', 'employee_transfer_details', ['employee_transfer_id'])


def downgrade() -> None:
    # Drop in reverse order (child tables first)

    # Lifecycle
    op.drop_table('employee_transfer_details')
    op.drop_table('employee_transfers')
    op.drop_table('employee_promotion_details')
    op.drop_table('employee_promotions')
    op.drop_table('employee_separation_activities')
    op.drop_table('employee_separations')
    op.drop_table('employee_onboarding_activities')
    op.drop_table('employee_onboardings')

    # Appraisal
    op.drop_table('appraisal_goals')
    op.drop_table('appraisals')
    op.drop_table('appraisal_template_goals')
    op.drop_table('appraisal_templates')

    # Training
    op.drop_table('training_results')
    op.drop_table('training_event_employees')
    op.drop_table('training_events')
    op.drop_table('training_programs')

    # Recruitment
    op.drop_table('job_offer_terms')
    op.drop_table('job_offers')
    op.drop_table('job_applicants')
    op.drop_table('job_openings')

    # Payroll
    op.drop_table('salary_slip_deductions')
    op.drop_table('salary_slip_earnings')
    op.drop_table('salary_slips')
    op.drop_table('payroll_entries')
    op.drop_table('salary_structure_assignments')
    op.drop_table('salary_structure_deductions')
    op.drop_table('salary_structure_earnings')
    op.drop_table('salary_structures')
    op.drop_table('salary_components')

    # Attendance
    op.drop_table('attendance_requests')
    op.drop_table('attendances')
    op.drop_table('shift_assignments')
    op.drop_table('shift_types')

    # Leave Management
    op.drop_table('leave_applications')
    op.drop_table('leave_allocations')
    op.drop_table('leave_policy_details')
    op.drop_table('leave_policies')
    op.drop_table('holidays')
    op.drop_table('holiday_lists')
    op.drop_table('leave_types')

    # Reference Data
    op.drop_table('employee_group_members')
    op.drop_table('employee_groups')
    op.drop_table('employee_grades')
