"""Support CSAT, Tags, and Ticket Enhancements.

Revision ID: 20241213_csat
Revises: 20241213_kb
Create Date: 2024-12-13

Phase 3 of helpdesk enhancement:
- CSAT surveys and responses
- Ticket tags
- Ticket custom fields
- Ticket enhancements (tags, watchers, merge support)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20241213_csat'
down_revision = '20241213_kb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # CSAT SURVEYS
    # ==========================================================================
    op.create_table(
        'csat_surveys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('survey_type', sa.String(20), default='csat', index=True),
        sa.Column('trigger', sa.String(30), default='ticket_resolved', index=True),
        sa.Column('questions', sa.JSON(), nullable=True),
        sa.Column('delay_hours', sa.Integer(), default=0),
        sa.Column('send_via', sa.String(50), default='email'),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, index=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # ==========================================================================
    # CSAT RESPONSES
    # ==========================================================================
    op.create_table(
        'csat_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('survey_id', sa.Integer(), sa.ForeignKey('csat_surveys.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('ticket_id', sa.Integer(), sa.ForeignKey('tickets.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('rating', sa.Integer(), nullable=True, index=True),
        sa.Column('answers', sa.JSON(), nullable=True),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('responded_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('response_channel', sa.String(50), nullable=True),
        sa.Column('response_token', sa.String(100), nullable=True, unique=True, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), index=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ==========================================================================
    # TICKET TAGS
    # ==========================================================================
    op.create_table(
        'ticket_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('usage_count', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True, index=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # ==========================================================================
    # TICKET CUSTOM FIELDS
    # ==========================================================================
    op.create_table(
        'ticket_custom_fields',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('field_key', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('field_type', sa.String(50), default='text'),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('default_value', sa.String(500), nullable=True),
        sa.Column('is_required', sa.Boolean(), default=False),
        sa.Column('min_length', sa.Integer(), nullable=True),
        sa.Column('max_length', sa.Integer(), nullable=True),
        sa.Column('regex_pattern', sa.String(500), nullable=True),
        sa.Column('display_order', sa.Integer(), default=100),
        sa.Column('show_in_list', sa.Boolean(), default=False),
        sa.Column('show_in_create', sa.Boolean(), default=True),
        sa.Column('is_active', sa.Boolean(), default=True, index=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # ==========================================================================
    # ALTER TICKETS TABLE - Add enhancement fields
    # ==========================================================================
    # Note: These columns may already exist; using batch mode for safety

    # Add tags column (JSON array of tag names)
    op.add_column('tickets', sa.Column('tags', sa.JSON(), nullable=True))

    # Add watchers column (JSON array of user IDs)
    op.add_column('tickets', sa.Column('watchers', sa.JSON(), nullable=True))

    # Add custom_fields column (JSON object with field_key -> value)
    op.add_column('tickets', sa.Column('custom_fields', sa.JSON(), nullable=True))

    # Add merge support
    op.add_column('tickets', sa.Column('merged_into_id', sa.Integer(), sa.ForeignKey('tickets.id', ondelete='SET NULL'), nullable=True))
    op.add_column('tickets', sa.Column('merged_tickets', sa.JSON(), nullable=True))  # IDs of tickets merged into this

    # Add parent ticket support for sub-tickets
    op.add_column('tickets', sa.Column('parent_ticket_id', sa.Integer(), sa.ForeignKey('tickets.id', ondelete='SET NULL'), nullable=True))

    # Add CSAT flag
    op.add_column('tickets', sa.Column('csat_sent', sa.Boolean(), default=False))
    op.add_column('tickets', sa.Column('csat_response_id', sa.Integer(), sa.ForeignKey('csat_responses.id', ondelete='SET NULL'), nullable=True))

    # Create indexes
    op.create_index('ix_tickets_merged_into_id', 'tickets', ['merged_into_id'])
    op.create_index('ix_tickets_parent_ticket_id', 'tickets', ['parent_ticket_id'])

    # ==========================================================================
    # SEED DATA: Default CSAT Survey
    # ==========================================================================
    op.execute("""
        INSERT INTO csat_surveys (name, description, survey_type, trigger, questions, delay_hours, send_via, is_active)
        VALUES (
            'Post-Resolution Survey',
            'Sent after a ticket is resolved to measure customer satisfaction',
            'csat',
            'ticket_resolved',
            '[{"id": "rating", "text": "How satisfied are you with the support you received?", "type": "rating", "required": true}, {"id": "feedback", "text": "Is there anything we could have done better?", "type": "text", "required": false}]',
            24,
            'email',
            true
        )
    """)

    # ==========================================================================
    # SEED DATA: Default Tags
    # ==========================================================================
    op.execute("""
        INSERT INTO ticket_tags (name, color, description, is_active)
        VALUES
            ('urgent', '#FF0000', 'Requires immediate attention', true),
            ('vip', '#FFD700', 'VIP customer ticket', true),
            ('billing', '#4169E1', 'Billing related issue', true),
            ('technical', '#228B22', 'Technical support issue', true),
            ('bug', '#DC143C', 'Software bug report', true),
            ('feature-request', '#9370DB', 'New feature request', true),
            ('follow-up', '#FF8C00', 'Needs follow-up action', true),
            ('escalated', '#8B0000', 'Has been escalated', true)
    """)


def downgrade() -> None:
    # Remove ticket enhancement columns
    op.drop_index('ix_tickets_parent_ticket_id', 'tickets')
    op.drop_index('ix_tickets_merged_into_id', 'tickets')
    op.drop_column('tickets', 'csat_response_id')
    op.drop_column('tickets', 'csat_sent')
    op.drop_column('tickets', 'parent_ticket_id')
    op.drop_column('tickets', 'merged_tickets')
    op.drop_column('tickets', 'merged_into_id')
    op.drop_column('tickets', 'custom_fields')
    op.drop_column('tickets', 'watchers')
    op.drop_column('tickets', 'tags')

    # Drop tables
    op.drop_table('ticket_custom_fields')
    op.drop_table('ticket_tags')
    op.drop_table('csat_responses')
    op.drop_table('csat_surveys')
