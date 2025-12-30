"""Add CRM tables - opportunities, activities, contacts, pipeline stages

Revision ID: crm_001
Revises:
Create Date: 2025-12-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'crm_001'
# Anchor CRM tables after the consolidated merge head
down_revision = '20250307_merge_all_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create opportunity_status enum
    op.execute("CREATE TYPE opportunitystatus AS ENUM ('open', 'won', 'lost')")

    # Create activity_type enum
    op.execute("CREATE TYPE activitytype AS ENUM ('call', 'meeting', 'email', 'task', 'note', 'demo', 'follow_up')")

    # Create activity_status enum
    op.execute("CREATE TYPE activitystatus AS ENUM ('planned', 'completed', 'cancelled')")

    # Create opportunity_stages table
    op.create_table(
        'opportunity_stages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('sequence', sa.Integer(), server_default='0', nullable=False, index=True),
        sa.Column('probability', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_won', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_lost', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('color', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create opportunities table
    op.create_table(
        'opportunities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        # Source - either a lead or existing customer
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('erpnext_leads.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True, index=True),
        # Pipeline
        sa.Column('stage_id', sa.Integer(), sa.ForeignKey('opportunity_stages.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('status', sa.Enum('open', 'won', 'lost', name='opportunitystatus', create_type=False),
                  server_default='open', nullable=False, index=True),
        # Deal value
        sa.Column('currency', sa.String(10), server_default='NGN', nullable=False),
        sa.Column('deal_value', sa.Numeric(18, 2), server_default='0', nullable=False),
        sa.Column('probability', sa.Integer(), server_default='0', nullable=False),
        sa.Column('weighted_value', sa.Numeric(18, 2), server_default='0', nullable=False),
        # Dates
        sa.Column('expected_close_date', sa.Date(), nullable=True, index=True),
        sa.Column('actual_close_date', sa.Date(), nullable=True),
        # Owner
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('sales_person_id', sa.Integer(), sa.ForeignKey('sales_persons.id', ondelete='SET NULL'), nullable=True, index=True),
        # Source/Campaign
        sa.Column('source', sa.String(255), nullable=True),
        sa.Column('campaign', sa.String(255), nullable=True),
        # Lost reason
        sa.Column('lost_reason', sa.Text(), nullable=True),
        sa.Column('competitor', sa.String(255), nullable=True),
        # Linked documents
        sa.Column('quotation_id', sa.Integer(), sa.ForeignKey('quotations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('sales_order_id', sa.Integer(), sa.ForeignKey('sales_orders.id', ondelete='SET NULL'), nullable=True),
        # ERPNext sync
        sa.Column('erpnext_id', sa.String(255), nullable=True, unique=True, index=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create contacts table
    op.create_table(
        'contacts',
        sa.Column('id', sa.Integer(), primary_key=True),
        # Linked to customer or lead
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('erpnext_leads.id', ondelete='CASCADE'), nullable=True, index=True),
        # Contact info
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('full_name', sa.String(255), nullable=False, index=True),
        # Contact details
        sa.Column('email', sa.String(255), nullable=True, index=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('mobile', sa.String(50), nullable=True),
        # Role/Position
        sa.Column('designation', sa.String(100), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        # Flags
        sa.Column('is_primary', sa.Boolean(), server_default='false', nullable=False, index=True),
        sa.Column('is_billing_contact', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_decision_maker', sa.Boolean(), server_default='false', nullable=False),
        # Status
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('unsubscribed', sa.Boolean(), server_default='false', nullable=False),
        # Social
        sa.Column('linkedin_url', sa.String(255), nullable=True),
        # Notes
        sa.Column('notes', sa.Text(), nullable=True),
        # ERPNext sync
        sa.Column('erpnext_id', sa.String(255), nullable=True, unique=True, index=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create activities table
    op.create_table(
        'activities',
        sa.Column('id', sa.Integer(), primary_key=True),
        # Activity info
        sa.Column('activity_type', sa.Enum('call', 'meeting', 'email', 'task', 'note', 'demo', 'follow_up',
                                            name='activitytype', create_type=False), nullable=False, index=True),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        # Status
        sa.Column('status', sa.Enum('planned', 'completed', 'cancelled', name='activitystatus', create_type=False),
                  server_default='planned', nullable=False, index=True),
        # Linked entities
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('erpnext_leads.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('opportunity_id', sa.Integer(), sa.ForeignKey('opportunities.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('contacts.id', ondelete='SET NULL'), nullable=True, index=True),
        # Scheduling
        sa.Column('scheduled_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        # Owner/Assignee
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('assigned_to_id', sa.Integer(), sa.ForeignKey('employees.id', ondelete='SET NULL'), nullable=True, index=True),
        # Call-specific
        sa.Column('call_direction', sa.String(20), nullable=True),
        sa.Column('call_outcome', sa.String(100), nullable=True),
        # Email-specific
        sa.Column('email_message_id', sa.String(255), nullable=True),
        # Priority
        sa.Column('priority', sa.String(20), nullable=True, server_default='medium'),
        # Reminder
        sa.Column('reminder_at', sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create lead_sources table
    op.create_table(
        'lead_sources',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # Create campaigns table
    op.create_table(
        'campaigns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('campaign_type', sa.String(100), nullable=True),
        # Dates
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        # Budget
        sa.Column('currency', sa.String(10), server_default='NGN', nullable=False),
        sa.Column('budget', sa.Numeric(18, 2), server_default='0', nullable=False),
        sa.Column('actual_cost', sa.Numeric(18, 2), server_default='0', nullable=False),
        # Metrics
        sa.Column('leads_generated', sa.Integer(), server_default='0', nullable=False),
        sa.Column('opportunities_generated', sa.Integer(), server_default='0', nullable=False),
        sa.Column('revenue_generated', sa.Numeric(18, 2), server_default='0', nullable=False),
        # Status
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        # ERPNext sync
        sa.Column('erpnext_id', sa.String(255), nullable=True, unique=True, index=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Seed default pipeline stages
    op.execute("""
        INSERT INTO opportunity_stages (name, sequence, probability, is_won, is_lost, color) VALUES
        ('Qualification', 0, 10, false, false, 'slate'),
        ('Needs Analysis', 1, 20, false, false, 'blue'),
        ('Proposal', 2, 40, false, false, 'amber'),
        ('Negotiation', 3, 60, false, false, 'orange'),
        ('Closed Won', 4, 100, true, false, 'emerald'),
        ('Closed Lost', 5, 0, false, true, 'red')
    """)

    # Seed default lead sources
    op.execute("""
        INSERT INTO lead_sources (name, description) VALUES
        ('Website', 'Leads from website contact form'),
        ('Referral', 'Customer or partner referrals'),
        ('Cold Call', 'Outbound cold calling'),
        ('Social Media', 'Facebook, LinkedIn, Twitter'),
        ('Email Campaign', 'Email marketing campaigns'),
        ('Trade Show', 'Events and trade shows'),
        ('Advertisement', 'Online or offline ads'),
        ('Partner', 'Channel partner leads')
    """)


def downgrade() -> None:
    op.drop_table('campaigns')
    op.drop_table('lead_sources')
    op.drop_table('activities')
    op.drop_table('contacts')
    op.drop_table('opportunities')
    op.drop_table('opportunity_stages')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS activitystatus')
    op.execute('DROP TYPE IF EXISTS activitytype')
    op.execute('DROP TYPE IF EXISTS opportunitystatus')
