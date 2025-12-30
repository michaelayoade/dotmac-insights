"""Add audit fields to HR models

Revision ID: 20241213_hr_audit
Revises: 20241215_hr_module
Create Date: 2024-12-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20241213_hr_audit'
# Chain after the HR base migration so referenced tables exist
down_revision = '20241215_hr_module'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # LeaveAllocation audit fields
    op.add_column('leave_allocations', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('leave_allocations', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('leave_allocations', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('leave_allocations', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # LeaveApplication audit fields
    op.add_column('leave_applications', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('leave_applications', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('leave_applications', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('leave_applications', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # Attendance audit fields
    op.add_column('attendances', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('attendances', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('attendances', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('attendances', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # AttendanceRequest audit fields
    op.add_column('attendance_requests', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('attendance_requests', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('attendance_requests', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('attendance_requests', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # JobOpening audit fields
    op.add_column('job_openings', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('job_openings', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('job_openings', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('job_openings', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # JobApplicant audit fields
    op.add_column('job_applicants', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('job_applicants', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('job_applicants', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('job_applicants', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # JobOffer audit fields
    op.add_column('job_offers', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('job_offers', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('job_offers', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('job_offers', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # PayrollEntry audit fields
    op.add_column('payroll_entries', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('payroll_entries', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('payroll_entries', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('payroll_entries', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # SalarySlip audit fields
    op.add_column('salary_slips', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('salary_slips', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('salary_slips', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('salary_slips', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # TrainingEvent audit fields
    op.add_column('training_events', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('training_events', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('training_events', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('training_events', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # TrainingResult audit fields
    op.add_column('training_results', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('training_results', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('training_results', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('training_results', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # Appraisal audit fields
    op.add_column('appraisals', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('appraisals', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('appraisals', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('appraisals', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # EmployeeOnboarding audit fields
    op.add_column('employee_onboardings', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_onboardings', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_onboardings', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_onboardings', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # EmployeeSeparation audit fields
    op.add_column('employee_separations', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_separations', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_separations', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_separations', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # EmployeePromotion audit fields
    op.add_column('employee_promotions', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_promotions', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_promotions', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_promotions', sa.Column('status_changed_at', sa.DateTime(), nullable=True))

    # EmployeeTransfer audit fields
    op.add_column('employee_transfers', sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_transfers', sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_transfers', sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('employee_transfers', sa.Column('status_changed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # EmployeeTransfer
    op.drop_column('employee_transfers', 'status_changed_at')
    op.drop_column('employee_transfers', 'status_changed_by_id')
    op.drop_column('employee_transfers', 'updated_by_id')
    op.drop_column('employee_transfers', 'created_by_id')

    # EmployeePromotion
    op.drop_column('employee_promotions', 'status_changed_at')
    op.drop_column('employee_promotions', 'status_changed_by_id')
    op.drop_column('employee_promotions', 'updated_by_id')
    op.drop_column('employee_promotions', 'created_by_id')

    # EmployeeSeparation
    op.drop_column('employee_separations', 'status_changed_at')
    op.drop_column('employee_separations', 'status_changed_by_id')
    op.drop_column('employee_separations', 'updated_by_id')
    op.drop_column('employee_separations', 'created_by_id')

    # EmployeeOnboarding
    op.drop_column('employee_onboardings', 'status_changed_at')
    op.drop_column('employee_onboardings', 'status_changed_by_id')
    op.drop_column('employee_onboardings', 'updated_by_id')
    op.drop_column('employee_onboardings', 'created_by_id')

    # Appraisal
    op.drop_column('appraisals', 'status_changed_at')
    op.drop_column('appraisals', 'status_changed_by_id')
    op.drop_column('appraisals', 'updated_by_id')
    op.drop_column('appraisals', 'created_by_id')

    # TrainingResult
    op.drop_column('training_results', 'status_changed_at')
    op.drop_column('training_results', 'status_changed_by_id')
    op.drop_column('training_results', 'updated_by_id')
    op.drop_column('training_results', 'created_by_id')

    # TrainingEvent
    op.drop_column('training_events', 'status_changed_at')
    op.drop_column('training_events', 'status_changed_by_id')
    op.drop_column('training_events', 'updated_by_id')
    op.drop_column('training_events', 'created_by_id')

    # SalarySlip
    op.drop_column('salary_slips', 'status_changed_at')
    op.drop_column('salary_slips', 'status_changed_by_id')
    op.drop_column('salary_slips', 'updated_by_id')
    op.drop_column('salary_slips', 'created_by_id')

    # PayrollEntry
    op.drop_column('payroll_entries', 'status_changed_at')
    op.drop_column('payroll_entries', 'status_changed_by_id')
    op.drop_column('payroll_entries', 'updated_by_id')
    op.drop_column('payroll_entries', 'created_by_id')

    # JobOffer
    op.drop_column('job_offers', 'status_changed_at')
    op.drop_column('job_offers', 'status_changed_by_id')
    op.drop_column('job_offers', 'updated_by_id')
    op.drop_column('job_offers', 'created_by_id')

    # JobApplicant
    op.drop_column('job_applicants', 'status_changed_at')
    op.drop_column('job_applicants', 'status_changed_by_id')
    op.drop_column('job_applicants', 'updated_by_id')
    op.drop_column('job_applicants', 'created_by_id')

    # JobOpening
    op.drop_column('job_openings', 'status_changed_at')
    op.drop_column('job_openings', 'status_changed_by_id')
    op.drop_column('job_openings', 'updated_by_id')
    op.drop_column('job_openings', 'created_by_id')

    # AttendanceRequest
    op.drop_column('attendance_requests', 'status_changed_at')
    op.drop_column('attendance_requests', 'status_changed_by_id')
    op.drop_column('attendance_requests', 'updated_by_id')
    op.drop_column('attendance_requests', 'created_by_id')

    # Attendance
    op.drop_column('attendances', 'status_changed_at')
    op.drop_column('attendances', 'status_changed_by_id')
    op.drop_column('attendances', 'updated_by_id')
    op.drop_column('attendances', 'created_by_id')

    # LeaveApplication
    op.drop_column('leave_applications', 'status_changed_at')
    op.drop_column('leave_applications', 'status_changed_by_id')
    op.drop_column('leave_applications', 'updated_by_id')
    op.drop_column('leave_applications', 'created_by_id')

    # LeaveAllocation
    op.drop_column('leave_allocations', 'status_changed_at')
    op.drop_column('leave_allocations', 'status_changed_by_id')
    op.drop_column('leave_allocations', 'updated_by_id')
    op.drop_column('leave_allocations', 'created_by_id')
