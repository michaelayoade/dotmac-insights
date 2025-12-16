"""Add full-text search for field service orders

Revision ID: fs002_fulltext_search
Revises: fs001_field_service
Create Date: 2025-12-16
"""
from alembic import op
import sqlalchemy as sa

revision = 'fs002_fulltext_search'
down_revision = 'fs001_field_service'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add full-text search column
    op.execute("""
        ALTER TABLE service_orders
        ADD COLUMN IF NOT EXISTS search_vector tsvector;
    """)

    # Create GIN index for full-text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_service_orders_search_vector
        ON service_orders USING GIN(search_vector);
    """)

    # Create function to update search vector
    op.execute("""
        CREATE OR REPLACE FUNCTION service_orders_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', COALESCE(NEW.order_number, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.service_address, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.city, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.customer_contact_name, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.resolution_notes, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.work_performed, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger to auto-update search vector
    op.execute("""
        DROP TRIGGER IF EXISTS service_orders_search_vector_trigger ON service_orders;
        CREATE TRIGGER service_orders_search_vector_trigger
        BEFORE INSERT OR UPDATE ON service_orders
        FOR EACH ROW
        EXECUTE FUNCTION service_orders_search_vector_update();
    """)

    # Backfill existing records
    op.execute("""
        UPDATE service_orders SET search_vector =
            setweight(to_tsvector('english', COALESCE(order_number, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(description, '')), 'B') ||
            setweight(to_tsvector('english', COALESCE(service_address, '')), 'C') ||
            setweight(to_tsvector('english', COALESCE(city, '')), 'C') ||
            setweight(to_tsvector('english', COALESCE(customer_contact_name, '')), 'B') ||
            setweight(to_tsvector('english', COALESCE(resolution_notes, '')), 'C') ||
            setweight(to_tsvector('english', COALESCE(work_performed, '')), 'C');
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS service_orders_search_vector_trigger ON service_orders;")
    op.execute("DROP FUNCTION IF EXISTS service_orders_search_vector_update();")
    op.execute("DROP INDEX IF EXISTS ix_service_orders_search_vector;")
    op.execute("ALTER TABLE service_orders DROP COLUMN IF EXISTS search_vector;")
