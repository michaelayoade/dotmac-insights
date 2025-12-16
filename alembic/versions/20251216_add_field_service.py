"""Add Field Service tables

Revision ID: fs001_field_service
Revises: 20250307_merge_all_heads
Create Date: 2025-12-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'fs001_field_service'
down_revision = '20250307_merge_all_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Service Zones
    op.create_table(
        'service_zones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('boundary_geojson', sa.Text(), nullable=True),
        sa.Column('center_latitude', sa.Numeric(), nullable=True),
        sa.Column('center_longitude', sa.Numeric(), nullable=True),
        sa.Column('coverage_areas', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('default_team_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_service_zones_code', 'service_zones', ['code'], unique=True)

    # Field Teams
    op.create_table(
        'field_teams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('coverage_zone_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('max_daily_orders', sa.Integer(), server_default='10'),
        sa.Column('supervisor_id', sa.Integer(), nullable=True),
        sa.Column('contact_phone', sa.String(50), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['supervisor_id'], ['employees.id']),
    )

    # Add default_team_id FK to service_zones
    op.create_foreign_key(
        'fk_service_zones_default_team',
        'service_zones', 'field_teams',
        ['default_team_id'], ['id']
    )

    # Field Team Members
    op.create_table(
        'field_team_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(50), server_default='technician'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('joined_date', sa.Date(), server_default=sa.func.current_date()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['team_id'], ['field_teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
    )
    op.create_index('ix_field_team_members_team_employee', 'field_team_members', ['team_id', 'employee_id'], unique=True)

    # Technician Skills
    op.create_table(
        'technician_skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('skill_type', sa.String(100), nullable=False),
        sa.Column('proficiency_level', sa.String(50), server_default='intermediate'),
        sa.Column('certification', sa.String(255), nullable=True),
        sa.Column('certification_number', sa.String(100), nullable=True),
        sa.Column('certification_date', sa.Date(), nullable=True),
        sa.Column('certification_expiry', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
    )
    op.create_index('ix_technician_skills_employee_skill', 'technician_skills', ['employee_id', 'skill_type'])

    # Checklist Templates
    op.create_table(
        'checklist_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('order_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_default', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_checklist_templates_order_type', 'checklist_templates', ['order_type'])

    # Checklist Template Items
    op.create_table(
        'checklist_template_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('idx', sa.Integer(), server_default='0'),
        sa.Column('item_text', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_required', sa.Boolean(), server_default='true'),
        sa.Column('requires_photo', sa.Boolean(), server_default='false'),
        sa.Column('requires_measurement', sa.Boolean(), server_default='false'),
        sa.Column('measurement_unit', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['checklist_templates.id'], ondelete='CASCADE'),
    )

    # Service Orders
    op.create_table(
        'service_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_number', sa.String(50), nullable=False),
        sa.Column('order_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), server_default='draft'),
        sa.Column('priority', sa.String(50), server_default='medium'),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('assigned_technician_id', sa.Integer(), nullable=True),
        sa.Column('assigned_team_id', sa.Integer(), nullable=True),
        sa.Column('zone_id', sa.Integer(), nullable=True),
        sa.Column('service_address', sa.Text(), nullable=False),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('latitude', sa.Numeric(), nullable=True),
        sa.Column('longitude', sa.Numeric(), nullable=True),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('scheduled_start_time', sa.Time(), nullable=True),
        sa.Column('scheduled_end_time', sa.Time(), nullable=True),
        sa.Column('estimated_duration_hours', sa.Numeric(), server_default='1'),
        sa.Column('actual_start_time', sa.DateTime(), nullable=True),
        sa.Column('actual_end_time', sa.DateTime(), nullable=True),
        sa.Column('travel_start_time', sa.DateTime(), nullable=True),
        sa.Column('arrival_time', sa.DateTime(), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('work_performed', sa.Text(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('customer_contact_name', sa.String(255), nullable=True),
        sa.Column('customer_contact_phone', sa.String(50), nullable=True),
        sa.Column('customer_contact_email', sa.String(255), nullable=True),
        sa.Column('customer_signature', sa.Text(), nullable=True),
        sa.Column('customer_signature_name', sa.String(255), nullable=True),
        sa.Column('customer_signed_at', sa.DateTime(), nullable=True),
        sa.Column('customer_rating', sa.Integer(), nullable=True),
        sa.Column('customer_feedback', sa.Text(), nullable=True),
        sa.Column('labor_cost', sa.Numeric(), server_default='0'),
        sa.Column('parts_cost', sa.Numeric(), server_default='0'),
        sa.Column('travel_cost', sa.Numeric(), server_default='0'),
        sa.Column('total_cost', sa.Numeric(), server_default='0'),
        sa.Column('billable_amount', sa.Numeric(), server_default='0'),
        sa.Column('is_billable', sa.Boolean(), server_default='true'),
        sa.Column('customer_notified', sa.Boolean(), server_default='false'),
        sa.Column('last_notification_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id']),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['assigned_technician_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['assigned_team_id'], ['field_teams.id']),
        sa.ForeignKeyConstraint(['zone_id'], ['service_zones.id']),
    )
    op.create_index('ix_service_orders_order_number', 'service_orders', ['order_number'], unique=True)
    op.create_index('ix_service_orders_order_type', 'service_orders', ['order_type'])
    op.create_index('ix_service_orders_status', 'service_orders', ['status'])
    op.create_index('ix_service_orders_priority', 'service_orders', ['priority'])
    op.create_index('ix_service_orders_scheduled', 'service_orders', ['scheduled_date', 'status'])
    op.create_index('ix_service_orders_customer', 'service_orders', ['customer_id', 'status'])
    op.create_index('ix_service_orders_technician', 'service_orders', ['assigned_technician_id', 'scheduled_date'])
    op.create_index('ix_service_orders_city', 'service_orders', ['city'])

    # Service Order Status History
    op.create_table(
        'service_order_status_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_order_id', sa.Integer(), nullable=False),
        sa.Column('from_status', sa.String(50), nullable=True),
        sa.Column('to_status', sa.String(50), nullable=False),
        sa.Column('changed_by', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('latitude', sa.Numeric(), nullable=True),
        sa.Column('longitude', sa.Numeric(), nullable=True),
        sa.Column('changed_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['service_order_id'], ['service_orders.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_service_order_status_history_order', 'service_order_status_history', ['service_order_id'])
    op.create_index('ix_service_order_status_history_changed_at', 'service_order_status_history', ['changed_at'])

    # Service Photos
    op.create_table(
        'service_photos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_order_id', sa.Integer(), nullable=False),
        sa.Column('photo_type', sa.String(50), server_default='issue'),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('thumbnail_path', sa.String(500), nullable=True),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('caption', sa.String(500), nullable=True),
        sa.Column('latitude', sa.Numeric(), nullable=True),
        sa.Column('longitude', sa.Numeric(), nullable=True),
        sa.Column('captured_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('uploaded_by', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['service_order_id'], ['service_orders.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_service_photos_order', 'service_photos', ['service_order_id'])

    # Service Checklists
    op.create_table(
        'service_checklists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_order_id', sa.Integer(), nullable=False),
        sa.Column('template_item_id', sa.Integer(), nullable=True),
        sa.Column('idx', sa.Integer(), server_default='0'),
        sa.Column('item_text', sa.String(500), nullable=False),
        sa.Column('is_required', sa.Boolean(), server_default='true'),
        sa.Column('is_completed', sa.Boolean(), server_default='false'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_by', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('measurement_value', sa.String(100), nullable=True),
        sa.Column('measurement_unit', sa.String(50), nullable=True),
        sa.Column('photo_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['service_order_id'], ['service_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_item_id'], ['checklist_template_items.id']),
        sa.ForeignKeyConstraint(['photo_id'], ['service_photos.id']),
    )
    op.create_index('ix_service_checklists_order', 'service_checklists', ['service_order_id'])

    # Service Time Entries
    op.create_table(
        'service_time_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_order_id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('entry_type', sa.String(50), server_default='work'),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('duration_hours', sa.Numeric(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_billable', sa.Boolean(), server_default='true'),
        sa.Column('start_latitude', sa.Numeric(), nullable=True),
        sa.Column('start_longitude', sa.Numeric(), nullable=True),
        sa.Column('end_latitude', sa.Numeric(), nullable=True),
        sa.Column('end_longitude', sa.Numeric(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['service_order_id'], ['service_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
    )
    op.create_index('ix_service_time_entries_order', 'service_time_entries', ['service_order_id'])
    op.create_index('ix_service_time_entries_employee', 'service_time_entries', ['employee_id'])

    # Service Order Items (Inventory)
    op.create_table(
        'service_order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_order_id', sa.Integer(), nullable=False),
        sa.Column('stock_item_id', sa.Integer(), nullable=True),
        sa.Column('item_code', sa.String(100), nullable=True),
        sa.Column('item_name', sa.String(255), nullable=False),
        sa.Column('quantity', sa.Numeric(), server_default='1'),
        sa.Column('unit', sa.String(50), server_default='pcs'),
        sa.Column('unit_cost', sa.Numeric(), server_default='0'),
        sa.Column('total_cost', sa.Numeric(), server_default='0'),
        sa.Column('serial_numbers', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_returned', sa.Boolean(), server_default='false'),
        sa.Column('returned_quantity', sa.Numeric(), nullable=True),
        sa.Column('return_notes', sa.Text(), nullable=True),
        sa.Column('added_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('added_by', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['service_order_id'], ['service_orders.id'], ondelete='CASCADE'),
        # NOTE: stock_items FK deferred - table not yet created by inventory module
        # sa.ForeignKeyConstraint(['stock_item_id'], ['stock_items.id']),
    )
    op.create_index('ix_service_order_items_order', 'service_order_items', ['service_order_id'])

    # Customer Notifications
    op.create_table(
        'customer_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('channel', sa.String(50), server_default='email'),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('short_message', sa.String(160), nullable=True),
        sa.Column('service_order_id', sa.Integer(), nullable=True),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('recipient_email', sa.String(255), nullable=True),
        sa.Column('recipient_phone', sa.String(50), nullable=True),
        sa.Column('recipient_name', sa.String(255), nullable=True),
        sa.Column('extra_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('attempt_count', sa.Integer(), server_default='0'),
        sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['service_order_id'], ['service_orders.id']),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id']),
    )
    op.create_index('ix_customer_notifications_customer', 'customer_notifications', ['customer_id'])
    op.create_index('ix_customer_notifications_type', 'customer_notifications', ['notification_type'])
    op.create_index('ix_customer_notifications_status', 'customer_notifications', ['status'])
    op.create_index('ix_customer_notifications_customer_type', 'customer_notifications', ['customer_id', 'notification_type'])
    op.create_index('ix_customer_notifications_status_scheduled', 'customer_notifications', ['status', 'scheduled_at'])

    # Customer Notification Preferences
    op.create_table(
        'customer_notification_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('email_enabled', sa.Boolean(), server_default='true'),
        sa.Column('sms_enabled', sa.Boolean(), server_default='false'),
        sa.Column('whatsapp_enabled', sa.Boolean(), server_default='false'),
        sa.Column('push_enabled', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
    )
    op.create_index('ix_customer_notif_prefs_customer_type', 'customer_notification_preferences', ['customer_id', 'notification_type'], unique=True)


def downgrade() -> None:
    op.drop_table('customer_notification_preferences')
    op.drop_table('customer_notifications')
    op.drop_table('service_order_items')
    op.drop_table('service_time_entries')
    op.drop_table('service_checklists')
    op.drop_table('service_photos')
    op.drop_table('service_order_status_history')
    op.drop_table('service_orders')
    op.drop_table('checklist_template_items')
    op.drop_table('checklist_templates')
    op.drop_table('technician_skills')
    op.drop_table('field_team_members')
    op.drop_constraint('fk_service_zones_default_team', 'service_zones', type_='foreignkey')
    op.drop_table('field_teams')
    op.drop_table('service_zones')
