"""Add Chatwoot sync ID fields to existing models

Revision ID: chatwoot_sync_001
Revises: f05939120634
Create Date: 2026-01-02 10:00:00.000000

Adds chatwoot_*_id fields to support syncing with Chatwoot:
- teams.chatwoot_team_id
- ticket_tags.chatwoot_label_id
- ticket_custom_fields.chatwoot_attribute_id
- canned_responses.chatwoot_id
- automation_rules.chatwoot_rule_id
- omni_channels.chatwoot_inbox_id
- csat_responses.chatwoot_conversation_id
- kb_categories.chatwoot_portal_slug, chatwoot_category_id
- kb_articles.chatwoot_article_id
"""
from alembic import op
import sqlalchemy as sa


revision = 'chatwoot_sync_001'
down_revision = 'f05939120634'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Teams - add Chatwoot team ID
    op.add_column('teams', sa.Column('chatwoot_team_id', sa.Integer(), nullable=True))
    op.add_column('teams', sa.Column('last_synced_at', sa.DateTime(), nullable=True))
    op.create_index('ix_teams_chatwoot_team_id', 'teams', ['chatwoot_team_id'], unique=True)

    # TicketTags - add Chatwoot label ID
    op.add_column('ticket_tags', sa.Column('chatwoot_label_id', sa.Integer(), nullable=True))
    op.add_column('ticket_tags', sa.Column('last_synced_at', sa.DateTime(), nullable=True))
    op.create_index('ix_ticket_tags_chatwoot_label_id', 'ticket_tags', ['chatwoot_label_id'], unique=True)

    # TicketCustomFields - add Chatwoot attribute ID
    op.add_column('ticket_custom_fields', sa.Column('chatwoot_attribute_id', sa.Integer(), nullable=True))
    op.create_index('ix_ticket_custom_fields_chatwoot_attribute_id', 'ticket_custom_fields', ['chatwoot_attribute_id'], unique=True)

    # CannedResponses - add Chatwoot ID
    op.add_column('canned_responses', sa.Column('chatwoot_id', sa.Integer(), nullable=True))
    op.add_column('canned_responses', sa.Column('last_synced_at', sa.DateTime(), nullable=True))
    op.create_index('ix_canned_responses_chatwoot_id', 'canned_responses', ['chatwoot_id'], unique=True)

    # AutomationRules - add Chatwoot rule ID
    op.add_column('automation_rules', sa.Column('chatwoot_rule_id', sa.Integer(), nullable=True))
    op.add_column('automation_rules', sa.Column('last_synced_at', sa.DateTime(), nullable=True))
    op.create_index('ix_automation_rules_chatwoot_rule_id', 'automation_rules', ['chatwoot_rule_id'], unique=True)

    # OmniChannels - add Chatwoot inbox ID
    op.add_column('omni_channels', sa.Column('chatwoot_inbox_id', sa.Integer(), nullable=True))
    op.create_index('ix_omni_channels_chatwoot_inbox_id', 'omni_channels', ['chatwoot_inbox_id'], unique=True)

    # CSATResponses - add Chatwoot conversation ID
    op.add_column('csat_responses', sa.Column('chatwoot_conversation_id', sa.Integer(), nullable=True))
    op.create_index('ix_csat_responses_chatwoot_conversation_id', 'csat_responses', ['chatwoot_conversation_id'])

    # KBCategories - add Chatwoot portal slug and category ID
    op.add_column('kb_categories', sa.Column('chatwoot_portal_slug', sa.String(255), nullable=True))
    op.add_column('kb_categories', sa.Column('chatwoot_category_id', sa.Integer(), nullable=True))
    op.add_column('kb_categories', sa.Column('last_synced_at', sa.DateTime(), nullable=True))
    op.create_index('ix_kb_categories_chatwoot_portal_slug', 'kb_categories', ['chatwoot_portal_slug'])
    op.create_index('ix_kb_categories_chatwoot_category_id', 'kb_categories', ['chatwoot_category_id'])

    # KBArticles - add Chatwoot article ID
    op.add_column('kb_articles', sa.Column('chatwoot_article_id', sa.Integer(), nullable=True))
    op.add_column('kb_articles', sa.Column('last_synced_at', sa.DateTime(), nullable=True))
    op.create_index('ix_kb_articles_chatwoot_article_id', 'kb_articles', ['chatwoot_article_id'], unique=True)


def downgrade() -> None:
    # KBArticles
    op.drop_index('ix_kb_articles_chatwoot_article_id', table_name='kb_articles')
    op.drop_column('kb_articles', 'last_synced_at')
    op.drop_column('kb_articles', 'chatwoot_article_id')

    # KBCategories
    op.drop_index('ix_kb_categories_chatwoot_category_id', table_name='kb_categories')
    op.drop_index('ix_kb_categories_chatwoot_portal_slug', table_name='kb_categories')
    op.drop_column('kb_categories', 'last_synced_at')
    op.drop_column('kb_categories', 'chatwoot_category_id')
    op.drop_column('kb_categories', 'chatwoot_portal_slug')

    # CSATResponses
    op.drop_index('ix_csat_responses_chatwoot_conversation_id', table_name='csat_responses')
    op.drop_column('csat_responses', 'chatwoot_conversation_id')

    # OmniChannels
    op.drop_index('ix_omni_channels_chatwoot_inbox_id', table_name='omni_channels')
    op.drop_column('omni_channels', 'chatwoot_inbox_id')

    # AutomationRules
    op.drop_index('ix_automation_rules_chatwoot_rule_id', table_name='automation_rules')
    op.drop_column('automation_rules', 'last_synced_at')
    op.drop_column('automation_rules', 'chatwoot_rule_id')

    # CannedResponses
    op.drop_index('ix_canned_responses_chatwoot_id', table_name='canned_responses')
    op.drop_column('canned_responses', 'last_synced_at')
    op.drop_column('canned_responses', 'chatwoot_id')

    # TicketCustomFields
    op.drop_index('ix_ticket_custom_fields_chatwoot_attribute_id', table_name='ticket_custom_fields')
    op.drop_column('ticket_custom_fields', 'chatwoot_attribute_id')

    # TicketTags
    op.drop_index('ix_ticket_tags_chatwoot_label_id', table_name='ticket_tags')
    op.drop_column('ticket_tags', 'last_synced_at')
    op.drop_column('ticket_tags', 'chatwoot_label_id')

    # Teams
    op.drop_index('ix_teams_chatwoot_team_id', table_name='teams')
    op.drop_column('teams', 'last_synced_at')
    op.drop_column('teams', 'chatwoot_team_id')
