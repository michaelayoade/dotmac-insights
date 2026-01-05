"""Add finance_validation_issues table."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260108_add_finance_validation_issues"
down_revision = "20260105_merge_all_heads_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_validation_issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("record_id", sa.BigInteger(), nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False, server_default="finance"),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_finance_validation_scope_detected",
        "finance_validation_issues",
        ["scope", "detected_at"],
        unique=False,
    )
    op.create_index(
        "ix_finance_validation_model_name",
        "finance_validation_issues",
        ["model_name"],
        unique=False,
    )
    op.create_index(
        "ix_finance_validation_record_id",
        "finance_validation_issues",
        ["record_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_finance_validation_issue",
        "finance_validation_issues",
        ["model_name", "record_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_finance_validation_issue", "finance_validation_issues", type_="unique")
    op.drop_index("ix_finance_validation_record_id", table_name="finance_validation_issues")
    op.drop_index("ix_finance_validation_model_name", table_name="finance_validation_issues")
    op.drop_index("ix_finance_validation_scope_detected", table_name="finance_validation_issues")
    op.drop_table("finance_validation_issues")
