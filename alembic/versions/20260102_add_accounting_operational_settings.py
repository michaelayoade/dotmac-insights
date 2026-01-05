"""add accounting operational settings

Revision ID: acct_ops_settings_001
Revises: 92f0d830518f
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'acct_ops_settings_001'
down_revision: Union[str, None] = '92f0d830518f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'accounting_operational_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company', sa.String(length=255), nullable=True, comment='Company scope (null = global defaults)'),

        # Aging Configuration
        sa.Column('aging_bucket_boundaries', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True, server_default='[0, 30, 60, 90]',
                  comment='Day boundaries for aging buckets (e.g., [0, 30, 60, 90])'),
        sa.Column('max_aging_invoices', sa.Integer(), nullable=False, server_default='10000',
                  comment='Maximum invoices to process in aging reports (DoS protection)'),

        # Attachment Settings
        sa.Column('upload_directory', sa.String(length=500), nullable=False,
                  server_default='/data/attachments', comment='Directory for file uploads'),
        sa.Column('max_file_size_mb', sa.Integer(), nullable=False, server_default='10',
                  comment='Maximum file upload size in MB'),
        sa.Column('allowed_extensions', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True,
                  server_default='[".pdf", ".png", ".jpg", ".jpeg", ".gif", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"]',
                  comment='Allowed file extensions for uploads'),

        # Cache TTL Settings
        sa.Column('dashboard_cache_ttl', sa.Integer(), nullable=False, server_default='60',
                  comment='Dashboard cache TTL in seconds'),
        sa.Column('report_cache_ttl', sa.Integer(), nullable=False, server_default='300',
                  comment='Report cache TTL in seconds'),
        sa.Column('aging_cache_ttl', sa.Integer(), nullable=False, server_default='60',
                  comment='Aging report cache TTL in seconds'),

        # Query/Security Limits
        sa.Column('max_gl_export_rows', sa.Integer(), nullable=False, server_default='10000',
                  comment='Maximum rows in GL export'),
        sa.Column('supplier_search_min_chars', sa.Integer(), nullable=False, server_default='2',
                  comment='Minimum characters required for supplier search (DoS protection)'),
        sa.Column('reconciliation_tolerance', sa.Numeric(precision=10, scale=4), nullable=False,
                  server_default='0.01', comment='Tolerance for reconciliation matching'),

        # Default Values
        sa.Column('default_currency', sa.String(length=3), nullable=False, server_default='NGN',
                  comment='Default currency code (ISO 4217)'),
        sa.Column('default_pagination_limit', sa.Integer(), nullable=False, server_default='50',
                  comment='Default pagination page size'),
        sa.Column('max_pagination_limit', sa.Integer(), nullable=False, server_default='500',
                  comment='Maximum pagination page size'),
        sa.Column('max_top_items', sa.Integer(), nullable=False, server_default='25',
                  comment='Maximum items for top N queries'),

        # Feature Flags
        sa.Column('enable_aging_cache', sa.Boolean(), nullable=False, server_default='true',
                  comment='Enable caching for aging reports'),
        sa.Column('enable_dashboard_cache', sa.Boolean(), nullable=False, server_default='true',
                  comment='Enable caching for dashboard'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company'),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id']),
        sa.CheckConstraint('max_file_size_mb > 0 AND max_file_size_mb <= 100'),
        sa.CheckConstraint('max_aging_invoices > 0 AND max_aging_invoices <= 100000'),
        sa.CheckConstraint('dashboard_cache_ttl >= 0 AND dashboard_cache_ttl <= 3600'),
        sa.CheckConstraint('report_cache_ttl >= 0 AND report_cache_ttl <= 3600'),
        sa.CheckConstraint('reconciliation_tolerance >= 0 AND reconciliation_tolerance <= 1'),
        sa.CheckConstraint('default_pagination_limit > 0 AND default_pagination_limit <= 1000'),
        sa.CheckConstraint('max_pagination_limit > 0 AND max_pagination_limit <= 10000'),
    )
    op.create_index('ix_acct_ops_settings_company', 'accounting_operational_settings', ['company'])

    # Insert global defaults row
    op.execute("""
        INSERT INTO accounting_operational_settings (company)
        VALUES (NULL)
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index('ix_acct_ops_settings_company', table_name='accounting_operational_settings')
    op.drop_table('accounting_operational_settings')
