"""Add vehicles table for fleet management

Revision ID: 20241220_add_vehicles
Revises: l7m8n9o0p1q2
Create Date: 2024-12-20 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20241220_add_vehicles'
down_revision = 'l7m8n9o0p1q2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create vehicles table
    op.create_table(
        'vehicles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('erpnext_id', sa.String(255), unique=True, index=True, nullable=True),

        # Basic Info
        sa.Column('license_plate', sa.String(50), nullable=False, index=True),
        sa.Column('make', sa.String(100), nullable=True, index=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('model_year', sa.Integer(), nullable=True),
        sa.Column('chassis_no', sa.String(100), nullable=True),
        sa.Column('color', sa.String(50), nullable=True),
        sa.Column('doors', sa.Integer(), nullable=True),
        sa.Column('wheels', sa.Integer(), nullable=True),

        # Value and Acquisition
        sa.Column('vehicle_value', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('acquisition_date', sa.Date(), nullable=True, index=True),

        # Fuel
        sa.Column('fuel_type', sa.String(50), nullable=True, index=True),
        sa.Column('fuel_uom', sa.String(20), nullable=True),

        # Odometer
        sa.Column('odometer_value', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('last_odometer_date', sa.Date(), nullable=True),
        sa.Column('uom', sa.String(20), nullable=True),

        # Insurance
        sa.Column('insurance_company', sa.String(255), nullable=True),
        sa.Column('policy_no', sa.String(100), nullable=True),
        sa.Column('insurance_start_date', sa.Date(), nullable=True),
        sa.Column('insurance_end_date', sa.Date(), nullable=True, index=True),

        # Driver Assignment
        sa.Column('employee', sa.String(255), nullable=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True, index=True),

        # Location and Company
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),

        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', index=True),
        sa.Column('docstatus', sa.Integer(), nullable=False, server_default='0'),

        # Sync metadata
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Composite indexes for common queries
    op.create_index('ix_vehicles_make_model', 'vehicles', ['make', 'model'])
    op.create_index('ix_vehicles_insurance_expiry', 'vehicles', ['is_active', 'insurance_end_date'])


def downgrade() -> None:
    op.drop_index('ix_vehicles_insurance_expiry', table_name='vehicles')
    op.drop_index('ix_vehicles_make_model', table_name='vehicles')
    op.drop_table('vehicles')
