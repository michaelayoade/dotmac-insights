"""Add Interview model, JobOffer expiry/void fields, expand enums

Revision ID: 20241214_002
Revises: 20241214_001
Create Date: 2024-12-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20241214_002'
down_revision: Union[str, None] = '20241214_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add expiry and void fields to job_offers table
    op.add_column('job_offers', sa.Column('expiry_date', sa.Date(), nullable=True))
    op.add_column('job_offers', sa.Column('voided_at', sa.DateTime(), nullable=True))
    op.add_column('job_offers', sa.Column('voided_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('job_offers', sa.Column('void_reason', sa.String(500), nullable=True))

    # Create interviews table
    op.create_table(
        'interviews',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('job_applicant_id', sa.Integer(), sa.ForeignKey('job_applicants.id'), nullable=False, index=True),
        sa.Column('scheduled_date', sa.DateTime(), nullable=False, index=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True, default=60),
        sa.Column('interviewer_id', sa.Integer(), sa.ForeignKey('employees.id'), nullable=True, index=True),
        sa.Column('interviewer_name', sa.String(255), nullable=True),
        sa.Column('interview_type', sa.String(100), nullable=True),
        sa.Column('location', sa.String(500), nullable=True),
        sa.Column('meeting_link', sa.String(500), nullable=True),
        sa.Column('status', sa.Enum('scheduled', 'completed', 'cancelled', 'no_show', name='interviewstatus'),
                  nullable=False, default='scheduled', index=True),
        sa.Column('result', sa.Enum('pass', 'fail', 'pending', name='interviewresult'), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('status_changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('status_changed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create index for interviews
    op.create_index('ix_interviews_applicant_date', 'interviews', ['job_applicant_id', 'scheduled_date'])

    # Note: JobApplicantStatus and JobOfferStatus use VARCHAR columns, not PostgreSQL enums.
    # New status values can be used directly without schema changes.


def downgrade() -> None:
    # Drop interviews table
    op.drop_index('ix_interviews_applicant_date', table_name='interviews')
    op.drop_table('interviews')

    # Drop enum types (created by the table)
    op.execute("DROP TYPE IF EXISTS interviewstatus")
    op.execute("DROP TYPE IF EXISTS interviewresult")

    # Remove expiry and void fields from job_offers table
    op.drop_column('job_offers', 'void_reason')
    op.drop_column('job_offers', 'voided_by_id')
    op.drop_column('job_offers', 'voided_at')
    op.drop_column('job_offers', 'expiry_date')

    # Note: Removing enum values from PostgreSQL is complex and not recommended
    # The new values will remain but won't cause issues
