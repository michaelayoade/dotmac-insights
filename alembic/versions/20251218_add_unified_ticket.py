"""Add unified_tickets table

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2025-12-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'm8n9o0p1q2r3'
down_revision = 'l7m8n9o0p1q2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types (IF NOT EXISTS pattern for PostgreSQL)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE unified_tickettype AS ENUM (
                'support', 'technical', 'billing', 'service',
                'complaint', 'inquiry', 'feature', 'bug'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE unified_ticketsource AS ENUM (
                'erpnext', 'splynx', 'chatwoot', 'email',
                'phone', 'web', 'api', 'internal'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE unified_ticketstatus AS ENUM (
                'open', 'in_progress', 'waiting', 'on_hold',
                'resolved', 'closed', 'reopened'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE unified_ticketpriority AS ENUM (
                'low', 'medium', 'high', 'urgent', 'critical'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE unified_ticketchannel AS ENUM (
                'email', 'phone', 'chat', 'whatsapp',
                'sms', 'web_form', 'api', 'in_person'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    # Create unified_tickets table
    # Use postgresql.ENUM with create_type=False since types already exist
    tickettype_enum = postgresql.ENUM(
        'support', 'technical', 'billing', 'service',
        'complaint', 'inquiry', 'feature', 'bug',
        name='unified_tickettype', create_type=False
    )
    ticketsource_enum = postgresql.ENUM(
        'erpnext', 'splynx', 'chatwoot', 'email',
        'phone', 'web', 'api', 'internal',
        name='unified_ticketsource', create_type=False
    )
    ticketchannel_enum = postgresql.ENUM(
        'email', 'phone', 'chat', 'whatsapp',
        'sms', 'web_form', 'api', 'in_person',
        name='unified_ticketchannel', create_type=False
    )
    ticketstatus_enum = postgresql.ENUM(
        'open', 'in_progress', 'waiting', 'on_hold',
        'resolved', 'closed', 'reopened',
        name='unified_ticketstatus', create_type=False
    )
    ticketpriority_enum = postgresql.ENUM(
        'low', 'medium', 'high', 'urgent', 'critical',
        name='unified_ticketpriority', create_type=False
    )

    op.create_table(
        'unified_tickets',
        # Primary key
        sa.Column('id', sa.Integer(), primary_key=True, index=True),

        # Type & Classification
        sa.Column('ticket_type', tickettype_enum,
                  nullable=False, server_default='support', index=True),
        sa.Column('source', ticketsource_enum,
                  nullable=False, server_default='internal', index=True),
        sa.Column('channel', ticketchannel_enum,
                  nullable=True),
        sa.Column('status', ticketstatus_enum,
                  nullable=False, server_default='open', index=True),
        sa.Column('priority', ticketpriority_enum,
                  nullable=False, server_default='medium', index=True),

        # Ticket Info
        sa.Column('ticket_number', sa.String(50), unique=True, index=True, nullable=True),
        sa.Column('subject', sa.String(500), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True, index=True),
        sa.Column('subcategory', sa.String(100), nullable=True),
        sa.Column('issue_type', sa.String(100), nullable=True),

        # Customer/Contact Reference
        sa.Column('unified_contact_id', sa.Integer(),
                  sa.ForeignKey('unified_contacts.id'), nullable=True, index=True),
        sa.Column('contact_name', sa.String(255), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True, index=True),
        sa.Column('contact_phone', sa.String(100), nullable=True),

        # Assignment & Ownership
        sa.Column('assigned_to_id', sa.Integer(),
                  sa.ForeignKey('employees.id'), nullable=True, index=True),
        sa.Column('assigned_team', sa.String(100), nullable=True, index=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', sa.Integer(),
                  sa.ForeignKey('employees.id'), nullable=True),

        # SLA Tracking
        sa.Column('response_by', sa.DateTime(), nullable=True, index=True),
        sa.Column('resolution_by', sa.DateTime(), nullable=True, index=True),
        sa.Column('first_response_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('response_sla_breached', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolution_sla_breached', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('first_response_time_seconds', sa.Integer(), nullable=True),
        sa.Column('resolution_time_seconds', sa.Integer(), nullable=True),
        sa.Column('total_time_open_seconds', sa.Integer(), nullable=True),

        # Resolution
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('resolution_type', sa.String(100), nullable=True),
        sa.Column('root_cause', sa.String(255), nullable=True),
        sa.Column('csat_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('csat_rating', sa.Integer(), nullable=True),
        sa.Column('csat_feedback', sa.Text(), nullable=True),

        # External System IDs
        sa.Column('splynx_id', sa.Integer(), unique=True, index=True, nullable=True),
        sa.Column('erpnext_id', sa.String(100), unique=True, index=True, nullable=True),
        sa.Column('chatwoot_conversation_id', sa.Integer(), unique=True, index=True, nullable=True),

        # Legacy table links
        sa.Column('legacy_ticket_id', sa.Integer(), index=True, nullable=True),
        sa.Column('legacy_conversation_id', sa.Integer(), index=True, nullable=True),
        sa.Column('legacy_omni_conversation_id', sa.Integer(), index=True, nullable=True),

        # Location/Context
        sa.Column('region', sa.String(100), nullable=True, index=True),
        sa.Column('base_station', sa.String(255), nullable=True),
        sa.Column('project_name', sa.String(255), nullable=True),

        # Metadata & Tags
        sa.Column('tags', postgresql.JSONB(), nullable=True),
        sa.Column('labels', postgresql.JSONB(), nullable=True),
        sa.Column('custom_fields', postgresql.JSONB(), nullable=True),
        sa.Column('internal_notes', sa.Text(), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('public_reply_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('internal_note_count', sa.Integer(), nullable=False, server_default='0'),

        # Ticket Relationships
        sa.Column('parent_ticket_id', sa.Integer(),
                  sa.ForeignKey('unified_tickets.id'), nullable=True, index=True),
        sa.Column('merged_into_id', sa.Integer(),
                  sa.ForeignKey('unified_tickets.id'), nullable=True),
        sa.Column('merged_ticket_ids', postgresql.JSONB(), nullable=True),

        # Sync & Outbound Tracking
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('splynx_sync_hash', sa.String(64), nullable=True),
        sa.Column('erpnext_sync_hash', sa.String(64), nullable=True),
        sa.Column('chatwoot_sync_hash', sa.String(64), nullable=True),
        sa.Column('last_synced_to_splynx', sa.DateTime(), nullable=True),
        sa.Column('last_synced_to_erpnext', sa.DateTime(), nullable=True),
        sa.Column('last_synced_to_chatwoot', sa.DateTime(), nullable=True),
        sa.Column('write_back_status', sa.String(50), nullable=True),
        sa.Column('write_back_error', sa.Text(), nullable=True),
        sa.Column('write_back_attempted_at', sa.DateTime(), nullable=True),

        # Audit & Soft Delete
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()'), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False,
                  server_default='false', index=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
    )

    # Keep only essential indexes (avoid bloat; composites cover most lookups)
    indexes = [
        # Singles
        ('ix_unified_tickets_parent_ticket_id', ['parent_ticket_id']),
        ('ix_unified_tickets_is_deleted', ['is_deleted']),
        ('ix_unified_tickets_created_at', ['created_at']),
        # Composites
        ('ix_unified_tickets_status_priority', ['status', 'priority']),
        ('ix_unified_tickets_assigned_status', ['assigned_to_id', 'status']),
        ('ix_unified_tickets_contact_status', ['unified_contact_id', 'status']),
        ('ix_unified_tickets_source_status', ['source', 'status']),
        ('ix_unified_tickets_created_status', ['created_at', 'status']),
        ('ix_unified_tickets_sla_response', ['response_by', 'response_sla_breached']),
        ('ix_unified_tickets_sla_resolution', ['resolution_by', 'resolution_sla_breached']),
    ]

    for name, cols in indexes:
        col_list = ", ".join(cols)
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON unified_tickets ({col_list})")


def downgrade() -> None:
    # Drop indexes
    for name in [
        'ix_unified_tickets_sla_resolution',
        'ix_unified_tickets_sla_response',
        'ix_unified_tickets_created_status',
        'ix_unified_tickets_source_status',
        'ix_unified_tickets_contact_status',
        'ix_unified_tickets_assigned_status',
        'ix_unified_tickets_status_priority',
        'ix_unified_tickets_parent_ticket_id',
        'ix_unified_tickets_is_deleted',
        'ix_unified_tickets_created_at',
    ]:
        op.execute(f"DROP INDEX IF EXISTS {name}")

    # Drop table
    op.drop_table('unified_tickets')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS unified_ticketchannel')
    op.execute('DROP TYPE IF EXISTS unified_ticketpriority')
    op.execute('DROP TYPE IF EXISTS unified_ticketstatus')
    op.execute('DROP TYPE IF EXISTS unified_ticketsource')
    op.execute('DROP TYPE IF EXISTS unified_tickettype')
