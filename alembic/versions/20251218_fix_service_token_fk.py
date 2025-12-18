"""fix_service_token_fk

Revision ID: 20251218_fix_svc_token_fk
Revises: 20251218_validate_checks
Create Date: 2025-12-18

Changes ServiceToken.created_by_id FK to SET NULL on user deletion.
This prevents orphaned service tokens when users are deleted.

Before: created_by_id FK with no action (blocks user deletion)
After: created_by_id FK with ON DELETE SET NULL (nullifies on user deletion)

Also makes created_by_id nullable to support the SET NULL action.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251218_fix_svc_token_fk"
down_revision: Union[str, None] = "20251218_validate_checks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change FK to SET NULL on delete."""

    # First, make created_by_id nullable if it isn't already
    op.alter_column(
        "service_tokens",
        "created_by_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # Drop existing FK constraint
    # Note: PostgreSQL auto-generates constraint names as "tablename_columnname_fkey"
    op.drop_constraint(
        "service_tokens_created_by_id_fkey",
        "service_tokens",
        type_="foreignkey",
    )

    # Re-create FK with ON DELETE SET NULL
    op.create_foreign_key(
        "service_tokens_created_by_id_fkey",
        "service_tokens",
        "users",
        ["created_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Also fix revoked_by_id FK if it doesn't have SET NULL
    op.drop_constraint(
        "service_tokens_revoked_by_id_fkey",
        "service_tokens",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "service_tokens_revoked_by_id_fkey",
        "service_tokens",
        "users",
        ["revoked_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Revert to original FK constraints (no ON DELETE action)."""

    # Drop SET NULL FK
    op.drop_constraint(
        "service_tokens_created_by_id_fkey",
        "service_tokens",
        type_="foreignkey",
    )

    # Re-create original FK (no ON DELETE)
    op.create_foreign_key(
        "service_tokens_created_by_id_fkey",
        "service_tokens",
        "users",
        ["created_by_id"],
        ["id"],
    )

    # Revert revoked_by_id FK
    op.drop_constraint(
        "service_tokens_revoked_by_id_fkey",
        "service_tokens",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "service_tokens_revoked_by_id_fkey",
        "service_tokens",
        "users",
        ["revoked_by_id"],
        ["id"],
    )

    # Note: created_by_id remains nullable since we can't
    # safely make it NOT NULL without risking data loss
