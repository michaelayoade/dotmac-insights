"""Add project management features: milestones, comments, activities

Revision ID: 20251223_add_project_pm_features
Revises: 20251222_add_fleet_rbac_scopes
Create Date: 2025-12-23

Adds:
- milestones table for project milestone tracking
- project_comments table for polymorphic comments on projects/tasks/milestones
- project_activities table for activity feed/audit trail
- milestone_id FK on tasks table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20251223_add_project_pm_features"
down_revision: Union[str, None] = "20251222_add_fleet_rbac_scopes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create milestone_status enum
    milestone_status = postgresql.ENUM(
        'planned', 'in_progress', 'completed', 'on_hold',
        name='milestonestatus',
        create_type=False
    )
    milestone_status.create(op.get_bind(), checkfirst=True)

    # Create project_activity_type enum
    project_activity_type = postgresql.ENUM(
        'created', 'updated', 'status_changed', 'assigned', 'comment_added',
        'attachment_added', 'milestone_completed', 'task_completed',
        'approval_submitted', 'approval_approved', 'approval_rejected',
        name='projectactivitytype',
        create_type=False
    )
    project_activity_type.create(op.get_bind(), checkfirst=True)

    # Create milestones table
    op.create_table(
        'milestones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('planned', 'in_progress', 'completed', 'on_hold', name='milestonestatus'), nullable=False, server_default='planned'),
        sa.Column('planned_start_date', sa.Date(), nullable=True),
        sa.Column('planned_end_date', sa.Date(), nullable=True),
        sa.Column('actual_start_date', sa.Date(), nullable=True),
        sa.Column('actual_end_date', sa.Date(), nullable=True),
        sa.Column('percent_complete', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('idx', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        # SoftDeleteMixin columns
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['deleted_by_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_milestones_id', 'milestones', ['id'])
    op.create_index('ix_milestones_project_id', 'milestones', ['project_id'])
    op.create_index('ix_milestones_status', 'milestones', ['status'])
    op.create_index('ix_milestones_planned_end_date', 'milestones', ['planned_end_date'])
    op.create_index('ix_milestones_is_deleted', 'milestones', ['is_deleted'])

    # Create project_comments table
    op.create_table(
        'project_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('author_name', sa.String(255), nullable=True),
        sa.Column('author_email', sa.String(255), nullable=True),
        sa.Column('is_edited', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('edited_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('company', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['deleted_by_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_project_comments_id', 'project_comments', ['id'])
    op.create_index('ix_project_comments_entity_type', 'project_comments', ['entity_type'])
    op.create_index('ix_project_comments_entity_id', 'project_comments', ['entity_id'])
    op.create_index('ix_project_comments_entity', 'project_comments', ['entity_type', 'entity_id'])
    op.create_index('ix_project_comments_author_id', 'project_comments', ['author_id'])
    op.create_index('ix_project_comments_created_at', 'project_comments', ['created_at'])
    op.create_index('ix_project_comments_is_deleted', 'project_comments', ['is_deleted'])

    # Create project_activities table
    op.create_table(
        'project_activities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('activity_type', sa.Enum(
            'created', 'updated', 'status_changed', 'assigned', 'comment_added',
            'attachment_added', 'milestone_completed', 'task_completed',
            'approval_submitted', 'approval_approved', 'approval_rejected',
            name='projectactivitytype'
        ), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('from_value', sa.Text(), nullable=True),
        sa.Column('to_value', sa.Text(), nullable=True),
        sa.Column('changed_fields', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('actor_name', sa.String(255), nullable=True),
        sa.Column('actor_email', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('audit_log_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['audit_log_id'], ['audit_logs.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_project_activities_id', 'project_activities', ['id'])
    op.create_index('ix_project_activities_entity_type', 'project_activities', ['entity_type'])
    op.create_index('ix_project_activities_entity_id', 'project_activities', ['entity_id'])
    op.create_index('ix_project_activities_entity', 'project_activities', ['entity_type', 'entity_id'])
    op.create_index('ix_project_activities_entity_created', 'project_activities', ['entity_type', 'entity_id', 'created_at'])
    op.create_index('ix_project_activities_activity_type', 'project_activities', ['activity_type'])
    op.create_index('ix_project_activities_actor_id', 'project_activities', ['actor_id'])
    op.create_index('ix_project_activities_created_at', 'project_activities', ['created_at'])

    # Add milestone_id FK to tasks table
    op.add_column('tasks', sa.Column('milestone_id', sa.Integer(), nullable=True))
    op.create_index('ix_tasks_milestone_id', 'tasks', ['milestone_id'])
    op.create_foreign_key(
        'fk_tasks_milestone_id',
        'tasks', 'milestones',
        ['milestone_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Remove milestone_id FK from tasks
    op.drop_constraint('fk_tasks_milestone_id', 'tasks', type_='foreignkey')
    op.drop_index('ix_tasks_milestone_id', table_name='tasks')
    op.drop_column('tasks', 'milestone_id')

    # Drop project_activities table and indexes
    op.drop_index('ix_project_activities_created_at', table_name='project_activities')
    op.drop_index('ix_project_activities_actor_id', table_name='project_activities')
    op.drop_index('ix_project_activities_activity_type', table_name='project_activities')
    op.drop_index('ix_project_activities_entity_created', table_name='project_activities')
    op.drop_index('ix_project_activities_entity', table_name='project_activities')
    op.drop_index('ix_project_activities_entity_id', table_name='project_activities')
    op.drop_index('ix_project_activities_entity_type', table_name='project_activities')
    op.drop_index('ix_project_activities_id', table_name='project_activities')
    op.drop_table('project_activities')

    # Drop project_comments table and indexes
    op.drop_index('ix_project_comments_is_deleted', table_name='project_comments')
    op.drop_index('ix_project_comments_created_at', table_name='project_comments')
    op.drop_index('ix_project_comments_author_id', table_name='project_comments')
    op.drop_index('ix_project_comments_entity', table_name='project_comments')
    op.drop_index('ix_project_comments_entity_id', table_name='project_comments')
    op.drop_index('ix_project_comments_entity_type', table_name='project_comments')
    op.drop_index('ix_project_comments_id', table_name='project_comments')
    op.drop_table('project_comments')

    # Drop milestones table and indexes
    op.drop_index('ix_milestones_is_deleted', table_name='milestones')
    op.drop_index('ix_milestones_planned_end_date', table_name='milestones')
    op.drop_index('ix_milestones_status', table_name='milestones')
    op.drop_index('ix_milestones_project_id', table_name='milestones')
    op.drop_index('ix_milestones_id', table_name='milestones')
    op.drop_table('milestones')

    # Drop enums
    project_activity_type = postgresql.ENUM(
        'created', 'updated', 'status_changed', 'assigned', 'comment_added',
        'attachment_added', 'milestone_completed', 'task_completed',
        'approval_submitted', 'approval_approved', 'approval_rejected',
        name='projectactivitytype'
    )
    project_activity_type.drop(op.get_bind(), checkfirst=True)

    milestone_status = postgresql.ENUM(
        'planned', 'in_progress', 'completed', 'on_hold',
        name='milestonestatus'
    )
    milestone_status.drop(op.get_bind(), checkfirst=True)
