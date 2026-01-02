"""enforce identity not nulls

Revision ID: 3b28128f2004
Revises: 2ef5a6fd4cf8
Create Date: 2026-01-02 11:31:27.641782

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3b28128f2004'
down_revision: Union[str, None] = '2ef5a6fd4cf8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE credentials SET mfa_enabled = false WHERE mfa_enabled IS NULL")
    op.execute("UPDATE credentials SET metadata = '{}'::jsonb WHERE metadata IS NULL")
    op.execute("UPDATE credentials SET created_at = now() WHERE created_at IS NULL")
    op.execute("UPDATE credentials SET updated_at = now() WHERE updated_at IS NULL")

    op.alter_column(
        "credentials",
        "mfa_enabled",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.alter_column(
        "credentials",
        "metadata",
        existing_type=postgresql.JSONB(),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column(
        "credentials",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "credentials",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    op.execute("UPDATE customer_account_contacts SET is_primary = false WHERE is_primary IS NULL")
    op.execute("UPDATE customer_account_contacts SET receives_invoices = false WHERE receives_invoices IS NULL")
    op.execute(
        "UPDATE customer_account_contacts SET receives_notifications = true WHERE receives_notifications IS NULL"
    )
    op.execute("UPDATE customer_account_contacts SET can_manage = false WHERE can_manage IS NULL")
    op.execute("UPDATE customer_account_contacts SET since = now() WHERE since IS NULL")

    op.alter_column(
        "customer_account_contacts",
        "is_primary",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.alter_column(
        "customer_account_contacts",
        "receives_invoices",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.alter_column(
        "customer_account_contacts",
        "receives_notifications",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    )
    op.alter_column(
        "customer_account_contacts",
        "can_manage",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.alter_column(
        "customer_account_contacts",
        "since",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    op.execute("UPDATE customer_account_resellers SET since = now() WHERE since IS NULL")
    op.execute("UPDATE customer_account_resellers SET metadata = '{}'::jsonb WHERE metadata IS NULL")

    op.alter_column(
        "customer_account_resellers",
        "since",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "customer_account_resellers",
        "metadata",
        existing_type=postgresql.JSONB(),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )

    op.execute("UPDATE customer_account_team SET is_primary = false WHERE is_primary IS NULL")
    op.execute("UPDATE customer_account_team SET since = now() WHERE since IS NULL")

    op.alter_column(
        "customer_account_team",
        "is_primary",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.alter_column(
        "customer_account_team",
        "since",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    op.execute("UPDATE customer_accounts SET currency = 'NGN' WHERE currency IS NULL")
    op.execute("UPDATE customer_accounts SET external_ids = '{}'::jsonb WHERE external_ids IS NULL")
    op.execute("UPDATE customer_accounts SET created_at = now() WHERE created_at IS NULL")

    op.alter_column(
        "customer_accounts",
        "currency",
        existing_type=sa.Text(),
        nullable=False,
        server_default="NGN",
    )
    op.alter_column(
        "customer_accounts",
        "external_ids",
        existing_type=postgresql.JSONB(),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column(
        "customer_accounts",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    op.execute("UPDATE memberships SET permissions = '[]'::jsonb WHERE permissions IS NULL")
    op.execute("UPDATE memberships SET created_at = now() WHERE created_at IS NULL")

    op.alter_column(
        "memberships",
        "permissions",
        existing_type=postgresql.JSONB(),
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    op.alter_column(
        "memberships",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    op.execute("UPDATE party_external_ids SET is_primary = false WHERE is_primary IS NULL")
    op.execute("UPDATE party_external_ids SET metadata = '{}'::jsonb WHERE metadata IS NULL")
    op.execute("UPDATE party_external_ids SET created_at = now() WHERE created_at IS NULL")
    op.execute("UPDATE party_external_ids SET updated_at = now() WHERE updated_at IS NULL")

    op.alter_column(
        "party_external_ids",
        "is_primary",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.alter_column(
        "party_external_ids",
        "metadata",
        existing_type=postgresql.JSONB(),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column(
        "party_external_ids",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "party_external_ids",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    op.execute("UPDATE party_relations SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE party_relations SET metadata = '{}'::jsonb WHERE metadata IS NULL")
    op.execute("UPDATE party_relations SET created_at = now() WHERE created_at IS NULL")

    op.alter_column(
        "party_relations",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    )
    op.alter_column(
        "party_relations",
        "metadata",
        existing_type=postgresql.JSONB(),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column(
        "party_relations",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    op.execute("UPDATE party_roles SET since = now() WHERE since IS NULL")
    op.execute("UPDATE party_roles SET metadata = '{}'::jsonb WHERE metadata IS NULL")
    op.execute("UPDATE party_roles SET created_at = now() WHERE created_at IS NULL")
    op.execute("UPDATE party_roles SET updated_at = now() WHERE updated_at IS NULL")

    op.alter_column(
        "party_roles",
        "since",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "party_roles",
        "metadata",
        existing_type=postgresql.JSONB(),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column(
        "party_roles",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "party_roles",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    op.execute("UPDATE ref_party_role_types SET sort_order = 0 WHERE sort_order IS NULL")
    op.execute("UPDATE ref_party_role_types SET is_active = true WHERE is_active IS NULL")

    op.alter_column(
        "ref_party_role_types",
        "sort_order",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )
    op.alter_column(
        "ref_party_role_types",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    )


def downgrade() -> None:
    op.alter_column(
        "ref_party_role_types",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "ref_party_role_types",
        "sort_order",
        existing_type=sa.Integer(),
        nullable=True,
        server_default=None,
    )

    op.alter_column(
        "party_roles",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "party_roles",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "party_roles",
        "metadata",
        existing_type=postgresql.JSONB(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "party_roles",
        "since",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )

    op.alter_column(
        "party_relations",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "party_relations",
        "metadata",
        existing_type=postgresql.JSONB(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "party_relations",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )

    op.alter_column(
        "party_external_ids",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "party_external_ids",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "party_external_ids",
        "metadata",
        existing_type=postgresql.JSONB(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "party_external_ids",
        "is_primary",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )

    op.alter_column(
        "memberships",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "memberships",
        "permissions",
        existing_type=postgresql.JSONB(),
        nullable=True,
        server_default=None,
    )

    op.alter_column(
        "customer_accounts",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "customer_accounts",
        "external_ids",
        existing_type=postgresql.JSONB(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "customer_accounts",
        "currency",
        existing_type=sa.Text(),
        nullable=True,
        server_default=None,
    )

    op.alter_column(
        "customer_account_team",
        "since",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "customer_account_team",
        "is_primary",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )

    op.alter_column(
        "customer_account_resellers",
        "metadata",
        existing_type=postgresql.JSONB(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "customer_account_resellers",
        "since",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )

    op.alter_column(
        "customer_account_contacts",
        "since",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "customer_account_contacts",
        "can_manage",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "customer_account_contacts",
        "receives_notifications",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "customer_account_contacts",
        "receives_invoices",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "customer_account_contacts",
        "is_primary",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )

    op.alter_column(
        "credentials",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "credentials",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "credentials",
        "metadata",
        existing_type=postgresql.JSONB(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "credentials",
        "mfa_enabled",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )
