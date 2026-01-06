"""Add party_id to users and backfill auth mappings

Revision ID: p1q2r3s4t5u6
Revises: 18f951bfba37
Create Date: 2025-01-10 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'p1q2r3s4t5u6'
down_revision = '18f951bfba37'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'party_id',
            sa.BigInteger(),
            sa.ForeignKey('parties.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index('ix_users_party_id', 'users', ['party_id'])

    connection = op.get_bind()
    users = connection.execute(
        sa.text(
            "SELECT id, email, name, external_id "
            "FROM users "
            "WHERE party_id IS NULL"
        )
    ).mappings().all()

    for row in users:
        existing_party_id = connection.execute(
            sa.text(
                "SELECT party_id FROM party_external_ids "
                "WHERE system = 'auth' AND external_id = :external_id"
            ),
            {"external_id": row["external_id"]},
        ).scalar()

        if existing_party_id:
            party_id = existing_party_id
        else:
            party_id = connection.execute(
                sa.text(
                    "INSERT INTO parties (type, name, primary_email) "
                    "VALUES (:type, :name, :email) "
                    "RETURNING id"
                ),
                {
                    "type": "person",
                    "name": row["name"] or row["email"],
                    "email": row["email"],
                },
            ).scalar_one()

            connection.execute(
                sa.text(
                    "INSERT INTO party_external_ids "
                    "(party_id, system, external_id, external_key_type, is_primary) "
                    "VALUES (:party_id, :system, :external_id, :external_key_type, true) "
                    "ON CONFLICT (system, external_id) DO NOTHING"
                ),
                {
                    "party_id": party_id,
                    "system": "auth",
                    "external_id": row["external_id"],
                    "external_key_type": "user_id",
                },
            )

        connection.execute(
            sa.text("UPDATE users SET party_id = :party_id WHERE id = :user_id"),
            {"party_id": party_id, "user_id": row["id"]},
        )


def downgrade() -> None:
    op.drop_index('ix_users_party_id', table_name='users')
    op.drop_column('users', 'party_id')
