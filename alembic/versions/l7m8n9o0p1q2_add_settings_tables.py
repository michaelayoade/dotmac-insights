"""Add general settings tables

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2024-12-14 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'l7m8n9o0p1q2'
down_revision = 'k6l7m8n9o0p1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create setting_groups table
    op.create_table(
        'setting_groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('group_name', sa.String(50), nullable=False, unique=True, index=True,
                  comment='Setting group identifier (email, payments, etc.)'),
        sa.Column('schema_version', sa.Integer(), nullable=False, server_default='1',
                  comment='Schema version for migration support'),
        sa.Column('data_encrypted', sa.Text(), nullable=False,
                  comment='OpenBao Transit encrypted JSON blob'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(),
                  onupdate=sa.func.now()),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )

    # Create settings_audit_log table
    op.create_table(
        'settings_audit_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('group_name', sa.String(50), nullable=False, index=True,
                  comment='Setting group that was modified'),
        sa.Column('action', sa.String(20), nullable=False,
                  comment='Action type: create, update, delete, test'),
        sa.Column('old_value_redacted', sa.Text(), nullable=True,
                  comment='Previous value with secrets redacted'),
        sa.Column('new_value_redacted', sa.Text(), nullable=True,
                  comment='New value with secrets redacted'),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('user_email', sa.String(255), nullable=False,
                  comment='Denormalized for query without join'),
        sa.Column('ip_address', sa.String(45), nullable=True,
                  comment='Client IP address'),
        sa.Column('user_agent', sa.String(500), nullable=True,
                  comment='Client user agent'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(),
                  index=True),
    )

    # Composite index for efficient queries
    op.create_index(
        'ix_settings_audit_group_created',
        'settings_audit_log',
        ['group_name', 'created_at']
    )


def downgrade() -> None:
    op.drop_index('ix_settings_audit_group_created', table_name='settings_audit_log')
    op.drop_table('settings_audit_log')
    op.drop_table('setting_groups')
