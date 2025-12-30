"""Support Knowledge Base and Canned Responses.

Revision ID: 20241213_kb
Revises: 20241213_automation_sla
Create Date: 2024-12-13

Phase 2 of helpdesk enhancement:
- Knowledge Base categories and articles
- Article attachments and feedback
- Canned responses (macros)
"""
from alembic import op, context
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20241213_kb'
# Phase 2 depends on the Phase 1 automation/SLA migration
down_revision = '20241213_support_automation_sla'
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_tables = set()
    inspector = None
    if not context.is_offline_mode():
        bind = op.get_bind()
        if bind:
            inspector = sa.inspect(bind)
            try:
                existing_tables = set(inspector.get_table_names())
            except Exception:
                existing_tables = set()

    def has_table(name: str) -> bool:
        if name in existing_tables:
            return True
        if inspector:
            try:
                return inspector.has_table(name)
            except Exception:
                pass
        # Fallback: use to_regclass
        try:
            bind = op.get_bind()
            if bind:
                for candidate in (name, f"public.{name}"):
                    res = bind.execute(sa.text("SELECT to_regclass(:n)"), {"n": candidate}).scalar()
                    if res:
                        return True
        except Exception:
            return False
        return False

    if has_table('kb_categories'):
        # Assume this migration already ran; skip to avoid duplicate tables.
        return

    # ==========================================================================
    # KNOWLEDGE BASE CATEGORIES
    # ==========================================================================
    if not has_table('kb_categories'):
        op.create_table(
            'kb_categories',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(255), nullable=False, index=True),
            sa.Column('slug', sa.String(255), nullable=False, unique=True, index=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('icon', sa.String(100), nullable=True),
            sa.Column('parent_id', sa.Integer(), sa.ForeignKey('kb_categories.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('display_order', sa.Integer(), default=100),
            sa.Column('visibility', sa.String(20), default='public', index=True),
            sa.Column('is_active', sa.Boolean(), default=True, index=True),
            sa.Column('created_by_id', sa.Integer(), nullable=True),
            sa.Column('updated_by_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
        )

    # ==========================================================================
    # KNOWLEDGE BASE ARTICLES
    # ==========================================================================
    if not has_table('kb_articles'):
        op.create_table(
            'kb_articles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(500), nullable=False, index=True),
            sa.Column('slug', sa.String(500), nullable=False, unique=True, index=True),
            sa.Column('category_id', sa.Integer(), sa.ForeignKey('kb_categories.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('excerpt', sa.String(500), nullable=True),
            sa.Column('status', sa.String(20), default='draft', index=True),
            sa.Column('visibility', sa.String(20), default='public', index=True),
            sa.Column('search_keywords', sa.Text(), nullable=True),
            sa.Column('view_count', sa.Integer(), default=0),
            sa.Column('helpful_count', sa.Integer(), default=0),
            sa.Column('not_helpful_count', sa.Integer(), default=0),
            sa.Column('version', sa.Integer(), default=1),
            sa.Column('published_at', sa.DateTime(), nullable=True),
            sa.Column('team_ids', sa.JSON(), nullable=True),
            sa.Column('related_article_ids', sa.JSON(), nullable=True),
            sa.Column('created_by_id', sa.Integer(), nullable=True),
            sa.Column('updated_by_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), index=True),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
        )

        op.execute("""
            CREATE INDEX ix_kb_articles_fulltext ON kb_articles
            USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '') || ' ' || coalesce(search_keywords, '')))
        """)

    # ==========================================================================
    # KNOWLEDGE BASE ATTACHMENTS
    # ==========================================================================
    if not has_table('kb_article_attachments'):
        op.create_table(
            'kb_article_attachments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('article_id', sa.Integer(), sa.ForeignKey('kb_articles.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('filename', sa.String(500), nullable=False),
            sa.Column('url', sa.String(2000), nullable=False),
            sa.Column('mime_type', sa.String(100), nullable=True),
            sa.Column('size_bytes', sa.Integer(), nullable=True),
            sa.Column('display_order', sa.Integer(), default=0),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
        )

    # ==========================================================================
    # KNOWLEDGE BASE FEEDBACK
    # ==========================================================================
    if not has_table('kb_article_feedback'):
        op.create_table(
            'kb_article_feedback',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('article_id', sa.Integer(), sa.ForeignKey('kb_articles.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('is_helpful', sa.Boolean(), nullable=False),
            sa.Column('feedback_text', sa.Text(), nullable=True),
            sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), index=True),
            sa.PrimaryKeyConstraint('id'),
        )

    # ==========================================================================
    # CANNED RESPONSES
    # ==========================================================================
    if not has_table('canned_responses'):
        op.create_table(
            'canned_responses',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(255), nullable=False, index=True),
            sa.Column('shortcode', sa.String(50), nullable=True, unique=True, index=True),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('scope', sa.String(20), default='personal', index=True),
            sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('category', sa.String(100), nullable=True, index=True),
            sa.Column('usage_count', sa.Integer(), default=0),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), default=True, index=True),
            sa.Column('created_by_id', sa.Integer(), nullable=True),
            sa.Column('updated_by_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
        )

    # ==========================================================================
    # SEED DATA: Default KB Categories
    # ==========================================================================
    op.execute("""
        INSERT INTO kb_categories (name, slug, description, display_order, visibility, is_active)
        VALUES
            ('General', 'general', 'General information and FAQs', 10, 'public', true),
            ('Getting Started', 'getting-started', 'Quick start guides and tutorials', 20, 'public', true),
            ('Billing', 'billing', 'Billing, payments, and invoices', 30, 'public', true),
            ('Technical Support', 'technical-support', 'Technical troubleshooting and guides', 40, 'public', true),
            ('Account Management', 'account-management', 'Account settings and profile management', 50, 'public', true),
            ('Internal Procedures', 'internal-procedures', 'Agent-only procedures and guidelines', 100, 'internal', true)
    """)

    # ==========================================================================
    # SEED DATA: Default Canned Responses
    # ==========================================================================
    op.execute("""
        INSERT INTO canned_responses (name, shortcode, content, scope, category, is_active)
        VALUES
            ('Greeting', '/hi', 'Hello {{customer_name}},\n\nThank you for contacting us. How can I assist you today?\n\nBest regards,\n{{agent_name}}', 'global', 'General', true),
            ('Thanks for Contact', '/thanks', 'Thank you for reaching out to us. We appreciate your patience as we look into this matter.\n\nBest regards,\n{{agent_name}}', 'global', 'General', true),
            ('Ticket Received', '/received', 'Hello {{customer_name}},\n\nWe have received your request (Ticket #{{ticket_id}}) and our team is reviewing it. We will get back to you as soon as possible.\n\nBest regards,\n{{agent_name}}', 'global', 'General', true),
            ('Need More Info', '/moreinfo', 'Hello {{customer_name}},\n\nThank you for your message. To better assist you, could you please provide the following information:\n\n1. [Specific information needed]\n2. [Additional details]\n\nBest regards,\n{{agent_name}}', 'global', 'General', true),
            ('Issue Resolved', '/resolved', 'Hello {{customer_name}},\n\nGreat news! The issue you reported has been resolved. Please let us know if you have any further questions or concerns.\n\nBest regards,\n{{agent_name}}', 'global', 'Resolution', true),
            ('Escalation Notice', '/escalated', 'Hello {{customer_name}},\n\nYour request has been escalated to our senior support team for further review. We will update you with progress as soon as we have more information.\n\nThank you for your patience.\n\nBest regards,\n{{agent_name}}', 'global', 'Escalation', true),
            ('Billing Inquiry', '/billing', 'Hello {{customer_name}},\n\nThank you for your billing inquiry. I will look into this matter and get back to you with the details.\n\nCould you please confirm:\n- Account/Invoice number\n- Specific charges in question\n\nBest regards,\n{{agent_name}}', 'global', 'Billing', true),
            ('Follow Up', '/followup', 'Hello {{customer_name}},\n\nI wanted to follow up on your recent request (Ticket #{{ticket_id}}). Has the issue been resolved to your satisfaction? Please let us know if you need any further assistance.\n\nBest regards,\n{{agent_name}}', 'global', 'General', true)
    """)


def downgrade() -> None:
    op.drop_table('canned_responses')
    op.drop_table('kb_article_feedback')
    op.drop_table('kb_article_attachments')
    op.execute('DROP INDEX IF EXISTS ix_kb_articles_fulltext')
    op.drop_table('kb_articles')
    op.drop_table('kb_categories')
