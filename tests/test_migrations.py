"""
Migration Smoke Tests

Tests that critical migrations can upgrade and downgrade cleanly (Postgres only).
Validates schema changes without requiring full data seeding.

Run with: poetry run pytest tests/test_migrations.py -v
"""

import os
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command

DATABASE_URL = (
    os.getenv("MIGRATION_TEST_DATABASE_URL")
    or os.getenv("TEST_DATABASE_URL")
    or os.getenv("DATABASE_URL")
)

if not DATABASE_URL or DATABASE_URL.startswith("sqlite"):
    pytest.skip(
        "Migration smoke tests require Postgres (set MIGRATION_TEST_DATABASE_URL).",
        allow_module_level=True,
    )


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def migration_db():
    """Create a database engine for Postgres migration testing."""
    engine = create_engine(DATABASE_URL)

    yield {"engine": engine, "url": DATABASE_URL}

    engine.dispose()


@pytest.fixture
def alembic_config(migration_db):
    """Create an Alembic config pointing to the test database."""
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", migration_db["url"])
    return config


# =============================================================================
# MIGRATION SMOKE TESTS
# =============================================================================


class TestMigrationSmoke:
    """Test critical migrations can upgrade and downgrade cleanly."""

    def test_payroll_config_upgrade_creates_tables(
        self, migration_db, alembic_config
    ):
        """Verify payroll_config migration creates expected tables and enums."""
        # Upgrade to payroll config migration
        command.upgrade(alembic_config, "m8n9o0p1q2r4")

        engine = migration_db["engine"]
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        # Assert tables created
        assert "payroll_regions" in tables
        assert "deduction_rules" in tables
        assert "tax_bands" in tables

        # Assert columns exist on payroll_regions
        columns = {c["name"] for c in inspector.get_columns("payroll_regions")}
        assert "code" in columns
        assert "name" in columns
        assert "currency" in columns
        assert "default_pay_frequency" in columns

        # Assert columns exist on deduction_rules
        columns = {c["name"] for c in inspector.get_columns("deduction_rules")}
        assert "region_id" in columns
        assert "code" in columns
        assert "deduction_type" in columns
        assert "calc_method" in columns
        assert "flat_amount" in columns
        assert "rate" in columns

    def test_payroll_config_downgrade_removes_tables(
        self, migration_db, alembic_config
    ):
        """Verify payroll_config downgrade removes tables."""
        # Upgrade first
        command.upgrade(alembic_config, "m8n9o0p1q2r4")

        engine = migration_db["engine"]
        inspector = inspect(engine)
        assert "payroll_regions" in inspector.get_table_names()

        # Downgrade to previous revision
        command.downgrade(alembic_config, "l7m8n9o0p1q2")

        # Refresh inspector
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        # Assert tables removed
        assert "payroll_regions" not in tables
        assert "deduction_rules" not in tables
        assert "tax_bands" not in tables

    def test_tax_config_upgrade_creates_tables(
        self, migration_db, alembic_config
    ):
        """Verify tax_config migration creates expected tables."""
        # Upgrade to tax config migration (includes payroll as dependency)
        command.upgrade(alembic_config, "n9o0p1q2r3s4")

        engine = migration_db["engine"]
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        # Assert tables created
        assert "tax_regions" in tables
        assert "taxconf_categories" in tables
        assert "taxconf_rates" in tables
        assert "taxconf_transactions" in tables
        assert "company_tax_settings" in tables

        # Assert columns on tax_regions
        columns = {c["name"] for c in inspector.get_columns("tax_regions")}
        assert "code" in columns
        assert "name" in columns
        assert "currency" in columns
        assert "default_sales_tax_rate" in columns
        assert "default_withholding_rate" in columns

    def test_tax_config_downgrade_removes_tables(
        self, migration_db, alembic_config
    ):
        """Verify tax_config downgrade removes tables."""
        # Upgrade first
        command.upgrade(alembic_config, "n9o0p1q2r3s4")

        engine = migration_db["engine"]
        inspector = inspect(engine)
        assert "tax_regions" in inspector.get_table_names()

        # Downgrade to payroll config revision
        command.downgrade(alembic_config, "m8n9o0p1q2r4")

        # Refresh inspector
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        # Assert tax tables removed
        assert "tax_regions" not in tables
        assert "taxconf_categories" not in tables
        assert "taxconf_rates" not in tables

        # Payroll tables should still exist
        assert "payroll_regions" in tables

    def test_migration_upgrade_head_completes(
        self, migration_db, alembic_config
    ):
        """Verify full upgrade to head completes without errors."""
        # This tests the entire migration chain
        command.upgrade(alembic_config, "head")

        engine = migration_db["engine"]
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        # Assert critical tables exist
        assert "alembic_version" in tables
        assert "users" in tables or len(tables) > 10  # Has significant schema

        # Verify we can query the version
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = [row[0] for row in result]
            assert len(versions) >= 1


# =============================================================================
# IDEMPOTENCY TESTS
# =============================================================================


class TestMigrationIdempotency:
    """Test migrations handle re-runs gracefully."""

    def test_upgrade_twice_is_safe(self, migration_db, alembic_config):
        """Running upgrade to same revision twice should be safe."""
        # First upgrade
        command.upgrade(alembic_config, "m8n9o0p1q2r4")

        engine = migration_db["engine"]
        inspector = inspect(engine)
        tables_after_first = set(inspector.get_table_names())

        # Second upgrade (should be no-op)
        command.upgrade(alembic_config, "m8n9o0p1q2r4")

        inspector = inspect(engine)
        tables_after_second = set(inspector.get_table_names())

        # Should be identical
        assert tables_after_first == tables_after_second

    def test_upgrade_downgrade_upgrade_cycle(self, migration_db, alembic_config):
        """Test up-down-up cycle completes without errors."""
        # Up
        command.upgrade(alembic_config, "m8n9o0p1q2r4")

        engine = migration_db["engine"]
        inspector = inspect(engine)
        assert "payroll_regions" in inspector.get_table_names()

        # Down
        command.downgrade(alembic_config, "l7m8n9o0p1q2")

        inspector = inspect(engine)
        assert "payroll_regions" not in inspector.get_table_names()

        # Up again
        command.upgrade(alembic_config, "m8n9o0p1q2r4")

        inspector = inspect(engine)
        assert "payroll_regions" in inspector.get_table_names()
