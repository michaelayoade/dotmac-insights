"""Add marketing module models

Revision ID: marketing_001
Revises: 20251217_merge_all_module_heads
Create Date: 2026-01-05 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'marketing_001'
down_revision = '20251217_merge_all_module_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    consent_channel_enum = postgresql.ENUM(
        'email',
        'whatsapp',
        name='consentchannel',
        create_type=False,
    )
    consent_status_enum = postgresql.ENUM(
        'granted',
        'revoked',
        'pending',
        'unknown',
        name='consentstatus',
        create_type=False,
    )
    consent_channel_enum.create(op.get_bind(), checkfirst=True)
    consent_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'marketing_campaigns',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('campaign_type', sa.Enum(
            'email', 'social', 'multi_channel', 'journey', 'paid_ad',
            name='marketingcampaigntype'
        ), nullable=False),
        sa.Column('status', sa.Enum(
            'draft', 'active', 'paused', 'completed', 'archived',
            name='marketingcampaignstatus'
        ), server_default='draft', nullable=False),
        sa.Column('budget', sa.Numeric(18, 2), server_default='0', nullable=True),
        sa.Column('currency', sa.String(10), server_default='NGN', nullable=False),
        sa.Column('utm_params', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('metrics', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_marketing_campaigns_type', 'marketing_campaigns', ['campaign_type'])
    op.create_index('ix_marketing_campaigns_status', 'marketing_campaigns', ['status'])

    op.create_table(
        'journey_templates',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_config', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('is_system_template', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'marketing_audiences',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('filter_criteria', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('member_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'email_templates',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('subject', sa.Text(), nullable=True),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('variables', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('is_system_template', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'customer_journeys',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('template_id', sa.BigInteger(), sa.ForeignKey('journey_templates.id'), nullable=True),
        sa.Column('campaign_id', sa.BigInteger(), sa.ForeignKey('marketing_campaigns.id'), nullable=True),
        sa.Column('status', sa.Enum(
            'draft', 'active', 'paused', 'completed', 'archived',
            name='journeystatus'
        ), server_default='draft', nullable=False),
        sa.Column('entry_trigger', sa.Text(), nullable=True),
        sa.Column('exit_conditions', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('metrics', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_customer_journeys_template', 'customer_journeys', ['template_id'])
    op.create_index('ix_customer_journeys_campaign', 'customer_journeys', ['campaign_id'])
    op.create_index('ix_customer_journeys_status', 'customer_journeys', ['status'])

    op.create_table(
        'journey_steps',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('journey_id', sa.BigInteger(), sa.ForeignKey('customer_journeys.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('step_type', sa.Enum(
            'email', 'whatsapp', 'social_post', 'wait', 'condition', 'split', 'webhook', 'task', 'exit',
            name='journeysteptype'
        ), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('delay_days', sa.Integer(), server_default='0', nullable=False),
        sa.Column('delay_hours', sa.Integer(), server_default='0', nullable=False),
        sa.Column('delay_minutes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('content', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('email_template_id', sa.BigInteger(), sa.ForeignKey('email_templates.id'), nullable=True),
        sa.Column('webhook_url', sa.Text(), nullable=True),
        sa.Column('condition_config', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_journey_steps_journey', 'journey_steps', ['journey_id'])
    op.create_index('ix_journey_steps_type', 'journey_steps', ['step_type'])

    op.create_table(
        'journey_enrollments',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('journey_id', sa.BigInteger(), sa.ForeignKey('customer_journeys.id', ondelete='CASCADE'), nullable=False),
        sa.Column('party_id', sa.BigInteger(), sa.ForeignKey('parties.id'), nullable=False),
        sa.Column('status', sa.Enum(
            'active', 'paused', 'completed', 'exited', 'failed',
            name='journeyenrollmentstatus'
        ), server_default='active', nullable=False),
        sa.Column('current_step_id', sa.BigInteger(), sa.ForeignKey('journey_steps.id', ondelete='SET NULL'), nullable=True),
        sa.Column('next_action_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('engagement', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_journey_enrollments_journey', 'journey_enrollments', ['journey_id'])
    op.create_index('ix_journey_enrollments_party', 'journey_enrollments', ['party_id'])
    op.create_index('ix_journey_enrollments_status', 'journey_enrollments', ['status'])
    op.create_index('ix_journey_enrollments_next_action', 'journey_enrollments', ['next_action_at'])

    op.create_table(
        'social_accounts',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('platform', sa.Enum(
            'facebook', 'instagram', 'twitter', 'linkedin', 'whatsapp',
            name='socialplatform'
        ), nullable=False),
        sa.Column('account_id', sa.String(255), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=True),
        sa.Column('profile_url', sa.Text(), nullable=True),
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stats', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('platform', 'account_id', name='uq_social_account_platform_id'),
    )
    op.create_index('ix_social_accounts_platform', 'social_accounts', ['platform'])

    op.create_table(
        'social_posts',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('account_id', sa.BigInteger(), sa.ForeignKey('social_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('media_urls', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum(
            'draft', 'scheduled', 'publishing', 'published', 'failed',
            name='socialpoststatus'
        ), server_default='draft', nullable=False),
        sa.Column('platform_post_id', sa.String(255), nullable=True),
        sa.Column('metrics', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_social_posts_account', 'social_posts', ['account_id'])
    op.create_index('ix_social_posts_status', 'social_posts', ['status'])
    op.create_index('ix_social_posts_scheduled', 'social_posts', ['scheduled_at'])

    op.create_table(
        'email_campaigns',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('template_id', sa.BigInteger(), sa.ForeignKey('email_templates.id'), nullable=False),
        sa.Column('audience_id', sa.BigInteger(), sa.ForeignKey('marketing_audiences.id'), nullable=True),
        sa.Column('campaign_id', sa.BigInteger(), sa.ForeignKey('marketing_campaigns.id'), nullable=True),
        sa.Column('status', sa.Enum(
            'draft', 'scheduled', 'sending', 'sent', 'paused', 'cancelled',
            name='emailcampaignstatus'
        ), server_default='draft', nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('timezone', sa.String(50), server_default='UTC', nullable=False),
        sa.Column('send_window_start', sa.Integer(), nullable=True),
        sa.Column('send_window_end', sa.Integer(), nullable=True),
        sa.Column('metrics', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_email_campaigns_template', 'email_campaigns', ['template_id'])
    op.create_index('ix_email_campaigns_audience', 'email_campaigns', ['audience_id'])
    op.create_index('ix_email_campaigns_campaign', 'email_campaigns', ['campaign_id'])
    op.create_index('ix_email_campaigns_status', 'email_campaigns', ['status'])
    op.create_index('ix_email_campaigns_scheduled', 'email_campaigns', ['scheduled_at'])

    op.create_table(
        'email_sends',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('campaign_id', sa.BigInteger(), sa.ForeignKey('email_campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('party_id', sa.BigInteger(), sa.ForeignKey('parties.id'), nullable=False),
        sa.Column('status', sa.Enum(
            'queued', 'sent', 'delivered', 'opened', 'clicked', 'bounced', 'failed', 'unsubscribed',
            name='emailsendstatus'
        ), server_default='queued', nullable=False),
        sa.Column('provider_message_id', sa.String(255), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bounced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tracking', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_email_sends_campaign', 'email_sends', ['campaign_id'])
    op.create_index('ix_email_sends_party', 'email_sends', ['party_id'])
    op.create_index('ix_email_sends_status', 'email_sends', ['status'])

    op.create_table(
        'marketing_integrations',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('integration_type', sa.String(50), nullable=False),
        sa.Column('credentials_encrypted', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum(
            'connected', 'disconnected', 'error', 'pending',
            name='marketingintegrationstatus'
        ), server_default='disconnected', nullable=False),
        sa.Column('settings', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_marketing_integrations_type', 'marketing_integrations', ['integration_type'])
    op.create_index('ix_marketing_integrations_status', 'marketing_integrations', ['status'])

    op.create_table(
        'marketing_consents',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('party_id', sa.BigInteger(), sa.ForeignKey('parties.id'), nullable=False),
        sa.Column('channel', consent_channel_enum, nullable=False),
        sa.Column('status', consent_status_enum, server_default='unknown', nullable=False),
        sa.Column('source', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('party_id', 'channel', name='uq_marketing_consent_party_channel'),
    )
    op.create_index('ix_marketing_consents_party', 'marketing_consents', ['party_id'])
    op.create_index('ix_marketing_consents_channel', 'marketing_consents', ['channel'])
    op.create_index('ix_marketing_consents_status', 'marketing_consents', ['status'])

    op.create_table(
        'marketing_suppressions',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('party_id', sa.BigInteger(), sa.ForeignKey('parties.id'), nullable=False),
        sa.Column('channel', consent_channel_enum, nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('source', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('party_id', 'channel', name='uq_marketing_suppression_party_channel'),
    )
    op.create_index('ix_marketing_suppressions_party', 'marketing_suppressions', ['party_id'])
    op.create_index('ix_marketing_suppressions_channel', 'marketing_suppressions', ['channel'])

    op.create_table(
        'marketing_webhook_events',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('event_id', sa.String(255), nullable=False),
        sa.Column('payload_hash', sa.String(64), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('platform', 'event_id', name='uq_marketing_webhook_platform_event'),
    )
    op.create_index(
        'ix_marketing_webhook_platform_received',
        'marketing_webhook_events',
        ['platform', 'received_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_marketing_webhook_platform_received', table_name='marketing_webhook_events')
    op.drop_table('marketing_webhook_events')

    op.drop_index('ix_marketing_suppressions_channel', table_name='marketing_suppressions')
    op.drop_index('ix_marketing_suppressions_party', table_name='marketing_suppressions')
    op.drop_table('marketing_suppressions')

    op.drop_index('ix_marketing_consents_status', table_name='marketing_consents')
    op.drop_index('ix_marketing_consents_channel', table_name='marketing_consents')
    op.drop_index('ix_marketing_consents_party', table_name='marketing_consents')
    op.drop_table('marketing_consents')

    op.drop_index('ix_marketing_integrations_status', table_name='marketing_integrations')
    op.drop_index('ix_marketing_integrations_type', table_name='marketing_integrations')
    op.drop_table('marketing_integrations')

    op.drop_index('ix_email_sends_status', table_name='email_sends')
    op.drop_index('ix_email_sends_party', table_name='email_sends')
    op.drop_index('ix_email_sends_campaign', table_name='email_sends')
    op.drop_table('email_sends')

    op.drop_index('ix_email_campaigns_scheduled', table_name='email_campaigns')
    op.drop_index('ix_email_campaigns_status', table_name='email_campaigns')
    op.drop_index('ix_email_campaigns_campaign', table_name='email_campaigns')
    op.drop_index('ix_email_campaigns_audience', table_name='email_campaigns')
    op.drop_index('ix_email_campaigns_template', table_name='email_campaigns')
    op.drop_table('email_campaigns')

    op.drop_index('ix_social_posts_scheduled', table_name='social_posts')
    op.drop_index('ix_social_posts_status', table_name='social_posts')
    op.drop_index('ix_social_posts_account', table_name='social_posts')
    op.drop_table('social_posts')

    op.drop_index('ix_social_accounts_platform', table_name='social_accounts')
    op.drop_table('social_accounts')

    op.drop_index('ix_journey_enrollments_next_action', table_name='journey_enrollments')
    op.drop_index('ix_journey_enrollments_status', table_name='journey_enrollments')
    op.drop_index('ix_journey_enrollments_party', table_name='journey_enrollments')
    op.drop_index('ix_journey_enrollments_journey', table_name='journey_enrollments')
    op.drop_table('journey_enrollments')

    op.drop_index('ix_journey_steps_type', table_name='journey_steps')
    op.drop_index('ix_journey_steps_journey', table_name='journey_steps')
    op.drop_table('journey_steps')

    op.drop_index('ix_customer_journeys_status', table_name='customer_journeys')
    op.drop_index('ix_customer_journeys_campaign', table_name='customer_journeys')
    op.drop_index('ix_customer_journeys_template', table_name='customer_journeys')
    op.drop_table('customer_journeys')

    op.drop_table('email_templates')
    op.drop_table('marketing_audiences')
    op.drop_table('journey_templates')

    op.drop_index('ix_marketing_campaigns_status', table_name='marketing_campaigns')
    op.drop_index('ix_marketing_campaigns_type', table_name='marketing_campaigns')
    op.drop_table('marketing_campaigns')

    consent_status_enum = postgresql.ENUM(
        'granted',
        'revoked',
        'pending',
        'unknown',
        name='consentstatus',
        create_type=False,
    )
    consent_channel_enum = postgresql.ENUM(
        'email',
        'whatsapp',
        name='consentchannel',
        create_type=False,
    )
    consent_status_enum.drop(op.get_bind(), checkfirst=True)
    consent_channel_enum.drop(op.get_bind(), checkfirst=True)
