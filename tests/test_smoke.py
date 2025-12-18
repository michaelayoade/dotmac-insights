"""Smoke tests for Dotmac Insights application.

These tests verify that the application boots correctly and key endpoints respond.
Run with: poetry run pytest tests/test_smoke.py -v
"""

import pytest
from fastapi.testclient import TestClient


class TestAppBoot:
    """Test that the application boots and imports work correctly."""

    def test_main_app_imports(self):
        """Test that the main app can be imported without errors."""
        from app.main import app
        assert app is not None
        assert app.title == "Dotmac Insights"

    def test_all_models_registered(self):
        """Test that all models are registered with Base.metadata."""
        from app.database import Base

        # Import models through the entrypoints
        from app.api.data_explorer import TABLES

        # Verify expected table count (update if models are added/removed)
        assert len(Base.metadata.tables) >= 45, (
            f"Expected at least 45 tables, got {len(Base.metadata.tables)}"
        )
        assert len(TABLES) >= 45, (
            f"Expected at least 45 TABLES entries, got {len(TABLES)}"
        )

    def test_celery_tasks_import(self):
        """Test that Celery tasks can be imported (loads all sync dependencies)."""
        from app.tasks.sync_tasks import (
            sync_splynx_customers,
            sync_erpnext_all,
            sync_chatwoot_contacts,
        )
        assert sync_splynx_customers is not None
        assert sync_erpnext_all is not None
        assert sync_chatwoot_contacts is not None

    def test_cli_imports(self):
        """Test that CLI can import all models."""
        # Simulate CLI import
        from app.models import Customer, Employee, Invoice, Department, SalesPerson
        assert Customer is not None
        assert Employee is not None
        assert Invoice is not None
        assert Department is not None
        assert SalesPerson is not None


class TestHealthEndpoints:
    """Test health and root endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_root_endpoint(self, client):
        """Test root endpoint returns app info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Dotmac Insights"
        assert data["status"] == "running"
        assert "version" in data

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        # Verify Prometheus format
        content = response.text
        assert "# HELP" in content or "prometheus_client" in content.lower(), (
            "Expected Prometheus metrics format or stub response"
        )

    def test_metrics_includes_auth_counters(self, client):
        """Test that auth failure metrics are defined."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        # If prometheus is available, should include our custom metrics
        if "# HELP" in content:
            assert "webhook_auth_failures" in content or "contacts_auth_failures" in content, (
                "Expected auth failure metrics to be defined"
            )


class TestDataExplorerEndpoints:
    """Test Data Explorer API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with API key header."""
        import os
        from app.main import app

        # Set a test API key if not already set
        api_key = os.environ.get("API_KEY", "test-api-key-for-tests")
        os.environ["API_KEY"] = api_key

        client = TestClient(app)
        # Add API key header for authenticated requests
        client.headers["X-API-Key"] = api_key
        return client

    def test_list_tables(self, client):
        """Test listing all available tables."""
        response = client.get("/api/explore/tables")
        assert response.status_code == 200
        data = response.json()

        # Verify expected tables exist
        expected_tables = [
            "customers", "employees", "invoices", "payments",
            "departments", "designations", "sales_persons", "sales_orders",
        ]
        for table in expected_tables:
            assert table in data, f"Expected table '{table}' not found"

    def test_explore_customers_table(self, client):
        """Test exploring the customers table."""
        response = client.get("/api/explore/tables/customers?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data
        assert data["table"] == "customers"

    def test_invalid_table_returns_404(self, client):
        """Test that invalid table name returns 404."""
        response = client.get("/api/explore/tables/nonexistent_table")
        assert response.status_code == 404


class TestModelRelationships:
    """Test that model relationships are properly configured."""

    def test_employee_hr_relationships(self):
        """Test Employee has HR relationship fields."""
        from app.models.employee import Employee

        # Check FK columns exist
        assert hasattr(Employee, "department_id")
        assert hasattr(Employee, "designation_id")
        assert hasattr(Employee, "reports_to_id")

        # Check relationships exist
        assert hasattr(Employee, "department_rel")
        assert hasattr(Employee, "designation_rel")
        assert hasattr(Employee, "manager")

    def test_sales_person_employee_relationship(self):
        """Test SalesPerson has Employee relationship."""
        from app.models.sales import SalesPerson

        assert hasattr(SalesPerson, "employee_id")
        assert hasattr(SalesPerson, "employee_rel")
